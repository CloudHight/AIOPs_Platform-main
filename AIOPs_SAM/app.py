"""
CloudWatch Anomaly Detection & Auto-Remediation System
Main Lambda Handler
"""

import os
import json
import time
import uuid
import boto3
import requests
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal
import aws_lambda_powertools as powertools
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.typing import LambdaContext
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException, Timeout, ConnectionError
from botocore.config import Config
from boto3.dynamodb.conditions import Attr

# Initialize AWS Lambda Powertools
logger = powertools.Logger(service="anomaly-detection")
tracer = powertools.Tracer()
metrics = powertools.Metrics(namespace="AnomalyDetection")

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 1
JIRA_API_TIMEOUT = 30
SAGEMAKER_TIMEOUT = 60

# AWS Clients
cloudwatch = boto3.client('cloudwatch')
cloudwatch_logs = boto3.client('logs')
sagemaker_config = Config(read_timeout=SAGEMAKER_TIMEOUT)
sagemaker = boto3.client('runtime.sagemaker', config=sagemaker_config)
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
sqs = boto3.client('sqs')
ssm = boto3.client('ssm')
events = boto3.client('events')
ec2 = boto3.client('ec2')
secretsmanager = boto3.client('secretsmanager')

# Environment Variables
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
PROCESSING_QUEUE_URL = os.environ['PROCESSING_QUEUE_URL']
DLQ_URL = os.environ['DLQ_URL']
EVENT_BUS_NAME = os.environ['EVENT_BUS_NAME']
CPU_MODEL_ENDPOINT = os.environ['CPU_MODEL_ENDPOINT']
LOG_MODEL_ENDPOINT = os.environ['LOG_MODEL_ENDPOINT']
JIRA_PROJECT_KEY = os.environ['JIRA_PROJECT_KEY']
JIRA_CREDENTIALS_SECRET = os.environ['JIRA_CREDENTIALS_SECRET']
JIRA_ISSUE_TYPE = os.environ.get('JIRA_ISSUE_TYPE', 'Incident')
INSTANCE_TAG_KEY = os.environ.get('INSTANCE_TAG_KEY', 'AnomalyMonitoring')
INSTANCE_TAG_VALUE = os.environ.get('INSTANCE_TAG_VALUE', 'enabled')
MONITORING_FREQUENCY = os.environ.get('MONITORING_FREQUENCY', 'rate(5 minutes)')
LOG_MIN_ANOMALOUS_LINES = int(os.environ.get('LOG_MIN_ANOMALOUS_LINES', '2'))
LOG_JIRA_MIN_ANOMALOUS_LINES = int(os.environ.get('LOG_JIRA_MIN_ANOMALOUS_LINES', '3'))
LOG_JIRA_SUPPRESSION_MINUTES = int(os.environ.get('LOG_JIRA_SUPPRESSION_MINUTES', '5'))
LOG_REPEAT_LOOKBACK_MINUTES = int(os.environ.get('LOG_REPEAT_LOOKBACK_MINUTES', '15'))

# Global configuration (fetched from SSM Parameter Store)
_config_cache = {}
_config_last_fetch = 0
CONFIG_CACHE_TTL = 300  # 5 minutes

@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection"""
    cpu_threshold: float = 0.50  # RCF score threshold (will be fine-tuned from new validation)
    log_threshold: float = 0.80
    grace_period_minutes: int = 15
    auto_remediation_enabled: bool = False
    dry_run: bool = True
    
    @classmethod
    def from_environment(cls):
        """Create config from environment variables"""
        auto_remediation_enabled = os.environ.get('AUTO_REMEDIATION_ENABLED', 'false').lower() == 'true'
        dry_run = os.environ.get('DRY_RUN', 'true').lower() == 'true'
        return cls(
            cpu_threshold=float(os.environ.get('ANOMALY_THRESHOLD_CPU', 0.50)),  # RCF score threshold
            log_threshold=float(os.environ.get('ANOMALY_THRESHOLD_LOG', 0.80)),
            grace_period_minutes=int(os.environ.get('GRACE_PERIOD_MINUTES', 15)),
            auto_remediation_enabled=auto_remediation_enabled,
            dry_run=dry_run
        )

class AnomalyDetectionError(Exception):
    """Base exception for anomaly detection errors"""
    pass

class JiraIntegrationError(AnomalyDetectionError):
    """Exception for Jira API failures"""
    pass

class SageMakerError(AnomalyDetectionError):
    """Exception for SageMaker inference failures"""
    pass

class DynamoDBError(AnomalyDetectionError):
    """Exception for DynamoDB operations"""
    pass


def _normalize_signature_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<ip>", text)
    text = re.sub(r"\b[a-f0-9]{8,32}\b", "<id>", text)
    text = re.sub(r"\b\d+\b", "<num>", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _get_current_anomaly_record(anomaly_id: str) -> Optional[Dict[str, Any]]:
    if not anomaly_id:
        return None
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        return table.get_item(Key={'anomaly_id': anomaly_id}).get('Item')
    except Exception as e:
        logger.error(f"Failed to load anomaly record {anomaly_id}: {str(e)}")
        return None


def _instance_is_remediation_eligible(instance_id: str) -> bool:
    if not instance_id:
        return False
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                state = instance.get('State', {}).get('Name')
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                monitoring_enabled = tags.get(INSTANCE_TAG_KEY) == INSTANCE_TAG_VALUE
                project_tagged = tags.get('Project') == 'AIOps'
                if state == 'running' and monitoring_enabled and project_tagged:
                    return True
                logger.warning(
                    f"Instance {instance_id} is not remediation eligible: "
                    f"state={state}, {INSTANCE_TAG_KEY}={tags.get(INSTANCE_TAG_KEY)}, Project={tags.get('Project')}"
                )
                return False
    except Exception as e:
        logger.error(f"Failed to validate remediation eligibility for {instance_id}: {str(e)}")
    return False


def _anomaly_record_allows_remediation(record: Optional[Dict[str, Any]], model_type: str) -> bool:
    if not record:
        logger.warning("Skipping remediation because the anomaly record could not be loaded")
        return False
    status = str(record.get('status', '')).lower()
    blocked_statuses = {
        'remediation_executed',
        'remediation_failed',
        'remediation_skipped',
        'resolved',
        'closed',
        'false_positive',
    }
    if status in blocked_statuses:
        logger.warning(f"Skipping remediation because anomaly status is {status}")
        return False
    if record.get('model_type') and record.get('model_type') != model_type:
        logger.warning(
            f"Skipping remediation because queued type {model_type} does not match "
            f"stored type {record.get('model_type')}"
        )
        return False
    max_attempts = int(os.environ.get('MAX_REMEDIATION_ATTEMPTS', '1'))
    attempts = int(record.get('remediation_attempts', 0))
    if attempts >= max_attempts:
        logger.warning(f"Skipping remediation because attempt limit is reached: {attempts}/{max_attempts}")
        return False
    return True

@tracer.capture_method
def get_config() -> AnomalyConfig:
    """Get configuration from SSM Parameter Store with caching"""
    global _config_cache, _config_last_fetch
    
    current_time = time.time()
    if current_time - _config_last_fetch < CONFIG_CACHE_TTL:
        return _config_cache.get('config', AnomalyConfig.from_environment())
    
    try:
        # Fetch parameters from SSM
        params = ssm.get_parameters_by_path(
            Path=f'/AnomalyDetection/{ENVIRONMENT}/',
            WithDecryption=True
        )
        
        config_dict = {}
        for param in params.get('Parameters', []):
            param_name = param['Name'].split('/')[-1]
            param_value = param['Value']
            
            if param_name == 'AutoRemediationEnabled':
                config_dict['auto_remediation_enabled'] = param_value.lower() == 'true'
            elif param_name == 'GracePeriodMinutes':
                config_dict['grace_period_minutes'] = int(param_value)
            elif param_name == 'DryRun':
                config_dict['dry_run'] = param_value.lower() == 'true'
        
        base_config = AnomalyConfig.from_environment()
        for key, value in config_dict.items():
            if hasattr(base_config, key):
                setattr(base_config, key, value)
        
        _config_cache['config'] = base_config
        _config_last_fetch = current_time
        
        logger.info(f"Loaded config from SSM: {config_dict}")
        return base_config
        
    except Exception as e:
        logger.warning(f"Failed to fetch config from SSM, using defaults: {str(e)}")
        return AnomalyConfig.from_environment()

@tracer.capture_method
def get_jira_credentials() -> Tuple[str, str, str]:
    """Retrieve Jira credentials from Secrets Manager"""
    try:
        response = secretsmanager.get_secret_value(SecretId=JIRA_CREDENTIALS_SECRET)
        secret = json.loads(response['SecretString'])
        
        api_url = secret.get('JIRA_API_URL', '')
        user_email = secret.get('JIRA_USER_EMAIL', '')
        api_token = secret.get('JIRA_API_TOKEN', '')
        
        if not all([api_url, user_email, api_token]):
            raise JiraIntegrationError("Incomplete Jira credentials in secret")
        
        return api_url, user_email, api_token
        
    except Exception as e:
        logger.error(f"Failed to get Jira credentials: {str(e)}")
        raise JiraIntegrationError(f"Could not retrieve Jira credentials: {str(e)}")

@tracer.capture_method
def get_instances_to_monitor() -> List[str]:
    """Get list of EC2 instance IDs to monitor based on tags"""
    try:
        instances = []
        
        # Find instances with the monitoring tag
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': f'tag:{INSTANCE_TAG_KEY}',
                    'Values': [INSTANCE_TAG_VALUE]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
        )
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                instances.append(instance_id)
                
                # Log instance details
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                logger.info(f"Found instance to monitor: {instance_id}, Tags: {tags}")
        
        logger.info(f"Total instances to monitor: {len(instances)}")
        return instances
        
    except Exception as e:
        logger.error(f"Failed to get instances: {str(e)}")
        # Return empty list to continue with other operations
        return []

@tracer.capture_method
def fetch_cpu_metrics(instance_id: str) -> List[float]:
    """Fetch CPU utilization metrics from CloudWatch"""
    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=15)  # Last 15 minutes
        
        response = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    'Id': 'cpu_utilization',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/EC2',
                            'MetricName': 'CPUUtilization',
                            'Dimensions': [
                                {
                                    'Name': 'InstanceId',
                                    'Value': instance_id
                                }
                            ]
                        },
                        'Period': 60,  # 1 minute intervals
                        'Stat': 'Average',
                        'Unit': 'Percent'
                    },
                    'ReturnData': True
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            ScanBy='TimestampDescending'
        )
        
        result = response['MetricDataResults'][0]
        values = result.get('Values', [])
        timestamps = result.get('Timestamps', [])

        if values:
            # Keep CPU points in chronological order so the latest value is last.
            if timestamps and len(timestamps) == len(values):
                ordered = sorted(zip(timestamps, values), key=lambda x: x[0])
                raw_values = [v for _, v in ordered]
            else:
                raw_values = values

            # Extract plain float values from CloudWatch response dicts
            # CloudWatch returns [{'Value': 45.2, 'Timestamp': ...}, ...]
            metrics = []
            for datapoint in raw_values:
                try:
                    if isinstance(datapoint, dict) and 'Value' in datapoint:
                        metrics.append(float(datapoint['Value']))
                    elif isinstance(datapoint, (int, float)):
                        metrics.append(float(datapoint))
                    else:
                        # Fallback: try to convert directly
                        metrics.append(float(datapoint))
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Could not extract value from datapoint {datapoint}: {e}")
                    continue
            
            if metrics:
                logger.debug(f"Fetched {len(metrics)} CPU metrics for {instance_id}: {metrics[:3]}")
                return metrics
            else:
                logger.warning(f"No valid CPU metrics extracted for instance {instance_id}")
                return []
        else:
            logger.warning(f"No CPU metrics found for instance {instance_id}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching CPU metrics for {instance_id}: {str(e)}")
        raise AnomalyDetectionError(f"CPU metrics fetch failed for {instance_id}: {str(e)}")

@tracer.capture_method(capture_response=False, capture_error=False)
def fetch_nginx_logs(instance_id: str) -> List[Dict[str, Any]]:
    """Fetch Nginx access and error logs from CloudWatch Logs"""
    try:
        log_group_prefix = os.environ.get('NGINX_LOG_GROUP_PREFIX', 'nginx/')
        try:
            groups_resp = cloudwatch_logs.describe_log_groups(
                logGroupNamePrefix=log_group_prefix,
                limit=10
            )
            log_groups = [g.get('logGroupName') for g in groups_resp.get('logGroups', []) if g.get('logGroupName')]
        except Exception:
            log_groups = []
        if not log_groups:
            log_groups = [
                "nginx/access.log",
                "nginx/error.log"
            ]
        
        all_logs = []
        end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_time = end_time - (15 * 60 * 1000)  # Last 15 minutes
        
        for log_group in log_groups:
            try:
                response = cloudwatch_logs.filter_log_events(
                    logGroupName=log_group,
                    logStreamNames=[instance_id],
                    startTime=start_time,
                    endTime=end_time,
                    filterPattern='error OR 500 OR 502 OR 503 OR 504 OR timeout OR failed',
                    limit=100
                )
                
                if response.get('events'):
                    all_logs.extend(response['events'])
                    logger.debug(f"Found {len(response['events'])} logs in {log_group}")
                else:
                    # Fallback 1: stream name prefix (some agents add suffix/prefix)
                    response = cloudwatch_logs.filter_log_events(
                        logGroupName=log_group,
                        logStreamNamePrefix=instance_id,
                        startTime=start_time,
                        endTime=end_time,
                        filterPattern='error OR 500 OR 502 OR 503 OR 504 OR timeout OR failed',
                        limit=100
                    )
                    if response.get('events'):
                        all_logs.extend(response['events'])
                        logger.debug(f"Found {len(response['events'])} logs in {log_group} via prefix")
                    else:
                        # Fallback 2: use latest streams if instance_id doesn't match
                        streams = cloudwatch_logs.describe_log_streams(
                            logGroupName=log_group,
                            orderBy='LastEventTime',
                            descending=True,
                            limit=5
                        ).get('logStreams', [])
                        stream_names = [s.get('logStreamName') for s in streams if s.get('logStreamName')]
                        if stream_names:
                            response = cloudwatch_logs.filter_log_events(
                                logGroupName=log_group,
                                logStreamNames=stream_names,
                                startTime=start_time,
                                endTime=end_time,
                                filterPattern='error OR 500 OR 502 OR 503 OR 504 OR timeout OR failed',
                                limit=100
                            )
                            if response.get('events'):
                                all_logs.extend(response['events'])
                                logger.debug(f"Found {len(response['events'])} logs in {log_group} via recent streams")
                            else:
                                # Fallback 3: no filter pattern to confirm any logs exist
                                response = cloudwatch_logs.filter_log_events(
                                    logGroupName=log_group,
                                    logStreamNames=stream_names,
                                    startTime=start_time,
                                    endTime=end_time,
                                    limit=100
                                )
                                if response.get('events'):
                                    all_logs.extend(response['events'])
                                    logger.debug(f"Found {len(response['events'])} logs in {log_group} without filter")
                    
            except cloudwatch_logs.exceptions.ResourceNotFoundException:
                continue  # Log group doesn't exist, try next one
            except Exception as e:
                logger.warning(f"Error fetching logs from {log_group}: {str(e)}")
                continue
        
        logger.info(f"Total Nginx logs fetched for {instance_id}: {len(all_logs)}")
        return all_logs
        
    except Exception as e:
        logger.error(f"Error fetching Nginx logs for {instance_id}: {str(e)}")
        raise AnomalyDetectionError(f"Nginx logs fetch failed for {instance_id}: {str(e)}")

@tracer.capture_method(capture_response=False, capture_error=False)
def invoke_sagemaker_model(endpoint_name: str, data: Dict[str, Any]) -> float:
    """Invoke SageMaker endpoint for anomaly detection using CSV format (like test script)"""
    for attempt in range(MAX_RETRIES):
        try:
            # Extract numeric values from data
            if isinstance(data.get('data'), list):
                values = []
                for v in data['data']:
                    try:
                        # Handle CloudWatch dict format {'Value': 45.2}
                        if isinstance(v, dict) and 'Value' in v:
                            values.append(float(v['Value']))
                        elif isinstance(v, dict):
                            numeric_vals = [val for val in v.values() if isinstance(val, (int, float))]
                            values.append(float(numeric_vals[0]) if numeric_vals else 0.0)
                        elif isinstance(v, (int, float)):
                            values.append(float(v))
                        elif isinstance(v, str):
                            values.append(float(v) if v else 0.0)
                        else:
                            values.append(0.0)
                    except (ValueError, TypeError, KeyError):
                        values.append(0.0)
            else:
                values = [float(data.get('data', 0.0))]
            
            if not values:
                logger.warning(f"No valid values extracted for {endpoint_name}")
                return 0.0
            
            # Convert to CSV format (newline-separated values)
            csv_body = '\n'.join(str(v) for v in values)
            logger.debug(f"Invoking {endpoint_name} with CSV format, {len(values)} values")
            
            response = sagemaker.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='text/csv',
                Accept='application/json',
                Body=csv_body
            )
            
            result = json.loads(response['Body'].read().decode('utf-8'))
            logger.debug(f"SageMaker response type: {type(result)}, content: {result}")
            
            # Parse response - RCF returns {'scores': [{'score': 0.92}, {'score': 0.15}, ...]}
            # Each score corresponds to one data point
            if isinstance(result, dict) and 'scores' in result:
                score_list = result['scores']
                logger.debug(f"Score list has {len(score_list) if isinstance(score_list, list) else 'unknown'} items")
                
                # Use latest score (last point in chronological input order).
                if isinstance(score_list, list) and score_list:
                    latest = score_list[-1]
                    logger.debug(f"Latest score item: {latest}")
                    
                    if isinstance(latest, dict) and 'score' in latest:
                        score = float(latest['score'])
                    elif isinstance(latest, (int, float)):
                        score = float(latest)
                    else:
                        logger.warning(f"Unexpected score format: {latest}")
                        score = 0.0
                else:
                    logger.warning(f"Empty score list: {score_list}")
                    score = 0.0
            elif isinstance(result, list) and result:
                first = result[0]
                if isinstance(first, dict) and 'score' in first:
                    score = float(first['score'])
                else:
                    score = float(first) if isinstance(first, (int, float)) else 0.0
            else:
                logger.warning(f"Unexpected response format: {type(result)}")
                score = 0.0
            
            logger.info(f"SageMaker inference score: {score:.4f} from {len(values)} data points, range: {min(values):.2f}%-{max(values):.2f}%")
            metrics.add_metric(name="SageMakerInvocations", unit="Count", value=1)
            return score
            
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed for {endpoint_name}, retrying in {wait_time}s: {str(e)}")
                time.sleep(wait_time)
            else:
                logger.error(f"All retries failed for SageMaker endpoint {endpoint_name}: {str(e)}")
                raise SageMakerError(f"Failed to invoke model {endpoint_name} after {MAX_RETRIES} attempts: {str(e)}")
    
    return 0.0

def _extract_log_predictions(result: Any, log_lines: List[str]) -> List[Dict[str, Any]]:
    """Extract per-line anomaly predictions from common text model response shapes."""
    predictions: List[Dict[str, Any]] = []
    try:
        if isinstance(result, list) and result:
            if all(isinstance(item, dict) for item in result):
                for idx, item in enumerate(result):
                    score = float(item.get('score', 0.0))
                    threshold = float(item.get('threshold', 0.5))
                    predictions.append({
                        'line': log_lines[idx] if idx < len(log_lines) else '',
                        'label': str(item.get('label', 'LABEL_0')).upper(),
                        'score': score,
                        'threshold': threshold,
                    })
                return predictions
            if isinstance(result[0], list):
                return _extract_log_predictions(result[0], log_lines)

        if isinstance(result, dict):
            labels = result.get('labels')
            scores = result.get('scores')
            threshold = float(result.get('threshold', 0.5))
            if isinstance(labels, list) and isinstance(scores, list):
                for idx, label in enumerate(labels[:len(scores)]):
                    predictions.append({
                        'line': log_lines[idx] if idx < len(log_lines) else '',
                        'label': str(label).upper(),
                        'score': float(scores[idx]),
                        'threshold': threshold,
                    })
                return predictions
            if 'score' in result:
                predictions.append({
                    'line': log_lines[0] if log_lines else '',
                    'label': str(result.get('label', 'LABEL_0')).upper(),
                    'score': float(result.get('score', 0.0)),
                    'threshold': float(result.get('threshold', 0.5)),
                })
                return predictions
    except Exception:
        return []
    return []


def _summarize_log_predictions(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize per-line anomaly predictions using count-based gating."""
    anomalous_lines = [
        item for item in predictions
        if item.get('label') == 'LABEL_1' and float(item.get('score', 0.0)) >= float(item.get('threshold', 0.5))
    ]
    top_anomalous_lines = sorted(
        anomalous_lines,
        key=lambda item: float(item.get('score', 0.0)),
        reverse=True
    )[:5]
    anomaly_scores = [float(item.get('score', 0.0)) for item in anomalous_lines]
    avg_anomaly_score = sum(anomaly_scores) / len(anomaly_scores) if anomaly_scores else 0.0
    max_anomaly_score = max(anomaly_scores) if anomaly_scores else 0.0
    threshold = float(predictions[0].get('threshold', 0.5)) if predictions else 0.5

    return {
        'predictions': predictions,
        'threshold': threshold,
        'anomalous_lines': anomalous_lines,
        'anomalous_line_count': len(anomalous_lines),
        'avg_anomaly_score': avg_anomaly_score,
        'max_anomaly_score': max_anomaly_score,
        'top_anomalous_lines': top_anomalous_lines,
        'decision_method': f'count>={LOG_MIN_ANOMALOUS_LINES}',
        'should_trigger_detection': len(anomalous_lines) >= LOG_MIN_ANOMALOUS_LINES,
    }


def _build_log_detection_signature(top_anomalous_lines: List[Dict[str, Any]]) -> str:
    snippets = []
    for item in top_anomalous_lines[:3]:
        line = item.get('line', '')
        normalized = _normalize_signature_text(line[:160])
        if normalized:
            snippets.append(normalized)
    return " | ".join(sorted(set(snippets)))


@tracer.capture_method(capture_response=False, capture_error=False)
def get_recent_log_anomaly_history(instance_id: str, detection_signature: str, lookback_minutes: int = 60) -> List[Dict[str, Any]]:
    """Fetch recent log anomaly records for deduplication and repeated-detection checks."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        response = table.scan(
            FilterExpression=(
                Attr('instance_id').eq(instance_id) &
                Attr('model_type').eq('log_anomaly') &
                Attr('environment').eq(ENVIRONMENT)
            )
        )
        items = response.get('Items', [])
        matches: List[Dict[str, Any]] = []
        for item in items:
            created_at = item.get('created_at') or item.get('timestamp')
            created_dt = _parse_iso_datetime(created_at)
            if not created_dt:
                continue
            if created_dt < cutoff:
                continue
            metadata = item.get('metadata', {}) or {}
            if metadata.get('detection_signature') == detection_signature:
                matches.append(item)
        return matches
    except Exception as e:
        logger.warning(f"Failed to fetch recent log anomaly history for {instance_id}: {str(e)}")
        return []

@tracer.capture_method(capture_response=False, capture_error=False)
def invoke_sagemaker_log_model(endpoint_name: str, log_lines: List[str]) -> Dict[str, Any]:
    """Invoke SageMaker text model endpoint for log anomaly detection."""
    for attempt in range(MAX_RETRIES):
        try:
            if not log_lines:
                logger.warning(f"No log lines provided for {endpoint_name}")
                return _summarize_log_predictions([])

            payload = {"inputs": log_lines}
            logger.debug(f"Invoking {endpoint_name} with JSON input, {len(log_lines)} lines")

            response = sagemaker.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Accept='application/json',
                Body=json.dumps(payload)
            )

            result = json.loads(response['Body'].read().decode('utf-8'))
            predictions = _extract_log_predictions(result, log_lines)
            analysis = _summarize_log_predictions(predictions)
            logger.info(
                "SageMaker log inference diagnostics: threshold=%s, anomalous_lines=%s/%s, "
                "avg_anomaly_score=%.4f, max_anomaly_score=%.4f, decision_method=%s",
                analysis['threshold'],
                analysis['anomalous_line_count'],
                len(log_lines),
                analysis['avg_anomaly_score'],
                analysis['max_anomaly_score'],
                analysis['decision_method'],
            )
            metrics.add_metric(name="SageMakerInvocations", unit="Count", value=1)
            return analysis

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed for {endpoint_name}, retrying in {wait_time}s: {str(e)[:500]}")
                time.sleep(wait_time)
            else:
                logger.error(f"All retries failed for SageMaker endpoint {endpoint_name}: {str(e)[:500]}")
                raise SageMakerError(f"Failed to invoke model {endpoint_name} after {MAX_RETRIES} attempts: {str(e)[:500]}")
    return _summarize_log_predictions([])

@tracer.capture_method
def store_inference_result(anomaly_data: Dict[str, Any]) -> str:
    """Store inference result in DynamoDB"""
    try:
        # Generate unique ID if not provided
        if 'anomaly_id' not in anomaly_data:
            anomaly_id = f"{anomaly_data.get('model_type', 'unknown')}-{anomaly_data.get('instance_id', 'unknown')}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
            anomaly_data['anomaly_id'] = anomaly_id
        
        # Add metadata
        anomaly_data['created_at'] = datetime.now(timezone.utc).isoformat()
        anomaly_data['environment'] = ENVIRONMENT
        anomaly_data['status'] = 'detected'
        
        # Set TTL (30 days from now)
        ttl_days = 30
        anomaly_data['ttl'] = int((datetime.now(timezone.utc) + timedelta(days=ttl_days)).timestamp())
        
        # Convert float to Decimal for DynamoDB
        anomaly_data = json.loads(json.dumps(anomaly_data), parse_float=Decimal)
        
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        response = table.put_item(Item=anomaly_data)
        
        logger.info(f"Stored anomaly result: {anomaly_data['anomaly_id']}")
        return anomaly_data['anomaly_id']
        
    except Exception as e:
        logger.error(f"Failed to store in DynamoDB: {str(e)}")
        raise DynamoDBError(f"DynamoDB store failed: {str(e)}")

@tracer.capture_method
def create_jira_ticket(anomaly_data: Dict[str, Any]) -> str:
    """Create Jira ticket for anomaly"""
    try:
        api_url, user_email, api_token = get_jira_credentials()
        
        # Prepare issue data
        instance_id = anomaly_data.get('instance_id', 'Unknown')
        model_type = anomaly_data.get('model_type', 'Unknown').replace('_', ' ').title()
        score = anomaly_data.get('inference_score', 0.0)
        timestamp = anomaly_data.get('timestamp', datetime.now(timezone.utc).isoformat())
        
        description_text = f"""
# Anomaly Detection Alert

Summary:
{model_type} detected on instance {instance_id} in {ENVIRONMENT} environment.

Details:
- Instance ID: {instance_id}
- Anomaly Type: {model_type}
- Confidence Score: {score:.4f}
- Detection Time: {timestamp}
- Environment: {ENVIRONMENT}
- Remediation Action: Auto-remediation scheduled after grace period

Metrics/Logs Analyzed:
{anomaly_data.get('data_summary', 'Not available')}

Next Steps:
1. Investigate the root cause
2. Review instance performance metrics
3. Check application logs
4. Monitor for recurrence

Auto-Remediation:
Auto-remediation will be triggered after the configured grace period unless manually intervened.

---
This ticket was automatically created by AWS Anomaly Detection System
""".strip()

        # Jira Cloud v3 requires description in Atlassian Document Format (ADF).
        def _to_adf(text: str) -> Dict[str, Any]:
            paragraphs = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                paragraphs.append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}]
                })
            return {"type": "doc", "version": 1, "content": paragraphs}

        issue_data = {
            "fields": {
                "project": {
                    "key": JIRA_PROJECT_KEY
                },
                "summary": f"[{ENVIRONMENT.upper()}] {model_type} detected on {instance_id}",
                "description": _to_adf(description_text),
                "issuetype": {
                    "name": JIRA_ISSUE_TYPE
                },
                "priority": {
                    "name": "High" if score > 0.9 else "Medium"
                },
                "labels": [
                    "auto-detected",
                    "anomaly",
                    "aws",
                    ENVIRONMENT,
                    model_type.lower().replace(' ', '-')
                ],
                "components": [
                    {
                        "name": "Infrastructure"
                    },
                    {
                        "name": "Monitoring"
                    }
                ]
            }
        }
        
        # Make API request - FIXED: Use correct REST API endpoint
        auth = HTTPBasicAuth(user_email, api_token)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Construct the correct REST API URL
        rest_api_url = f"{api_url}/rest/api/3/issue"
        logger.debug(f"Calling Jira API: {rest_api_url}")
        logger.debug(f"Issue payload: {json.dumps(issue_data, indent=2)}")
        
        response = requests.post(
            rest_api_url,
            json=issue_data,
            headers=headers,
            auth=auth,
            timeout=JIRA_API_TIMEOUT
        )
        
        response.raise_for_status()
        result = response.json()
        
        ticket_id = result.get('key', '')
        ticket_url = f"{api_url.replace('/rest/api/3', '')}/browse/{ticket_id}"
        
        logger.info(f"Created Jira ticket: {ticket_id} - {ticket_url}")
        metrics.add_metric(name="JiraTicketsCreated", unit="Count", value=1)
        
        return ticket_id
        
    except RequestException as e:
        logger.error(f"Jira API request failed: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text[:1000]}")  # Full response for debugging
        raise JiraIntegrationError(f"Jira API failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create Jira ticket: {str(e)}")
        raise JiraIntegrationError(f"Jira ticket creation failed: {str(e)}")

@tracer.capture_method
def send_team_notification(anomaly_data: Dict[str, Any], jira_ticket_id: str) -> None:
    """Send email notification via SNS"""
    try:
        config = get_config()
        
        instance_id = anomaly_data.get('instance_id', 'Unknown')
        model_type = anomaly_data.get('model_type', 'Unknown').replace('_', ' ').title()
        score = anomaly_data.get('inference_score', 0.0)
        
        # Calculate auto-remediation time
        grace_end = datetime.now(timezone.utc) + timedelta(minutes=config.grace_period_minutes)
        
        message = {
            "default": f"Anomaly detected on {instance_id}",
            "email": json.dumps({
                "subject": f"[{ENVIRONMENT.upper()}] {model_type} Alert - {instance_id}",
                "body": f"""
ANOMALY DETECTION ALERT

Environment: {ENVIRONMENT}
Instance: {instance_id}
Anomaly Type: {model_type}
Confidence Score: {score:.4f}
Detection Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

Jira Ticket: {jira_ticket_id}
Auto-Remediation Scheduled: {grace_end.strftime('%Y-%m-%d %H:%M:%S UTC')}

ACTION REQUIRED:
Please investigate this anomaly within the next {config.grace_period_minutes} minutes.
If no action is taken, auto-remediation will be triggered automatically.

---
AWS Anomaly Detection System
This is an automated message.
""",
                "instance_id": instance_id,
                "anomaly_type": model_type,
                "score": score,
                "jira_ticket": jira_ticket_id,
                "grace_period_end": grace_end.isoformat(),
                "environment": ENVIRONMENT
            }, indent=2)
        }
        
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[{ENVIRONMENT.upper()}] {model_type} Alert - {instance_id}",
            Message=json.dumps(message),
            MessageStructure='json',
            MessageAttributes={
                'environment': {
                    'DataType': 'String',
                    'StringValue': ENVIRONMENT
                },
                'severity': {
                    'DataType': 'String',
                    'StringValue': 'HIGH' if score > 0.9 else 'MEDIUM'
                },
                'anomaly_type': {
                    'DataType': 'String',
                    'StringValue': model_type
                }
            }
        )
        
        logger.info(f"Sent SNS notification for anomaly {anomaly_data.get('anomaly_id')}")
        metrics.add_metric(name="SNSNotificationsSent", unit="Count", value=1)
        
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")
        # Don't raise, continue with processing

@tracer.capture_method
def emit_eventbridge_event(anomaly_data: Dict[str, Any], event_type: str) -> None:
    """Emit event to EventBridge"""
    try:
        event_detail = {
            'anomaly_id': anomaly_data.get('anomaly_id'),
            'instance_id': anomaly_data.get('instance_id'),
            'anomaly_type': anomaly_data.get('model_type'),
            'score': float(anomaly_data.get('inference_score', 0.0)),
            'threshold': float(anomaly_data.get('threshold', 0.0)),
            'timestamp': anomaly_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'jira_ticket_id': anomaly_data.get('jira_ticket_id', ''),
            'environment': ENVIRONMENT,
            'metadata': anomaly_data.get('metadata', {})
        }
        
        response = events.put_events(
            Entries=[
                {
                    'Source': f"anomaly-detection.{ENVIRONMENT}",
                    'DetailType': event_type,
                    'Detail': json.dumps(event_detail),
                    'EventBusName': EVENT_BUS_NAME,
                    'Time': datetime.now(timezone.utc)
                }
            ]
        )
        
        if response['FailedEntryCount'] > 0:
            logger.error(f"Failed to emit EventBridge event: {response['Entries']}")
        else:
            logger.debug(f"Emitted EventBridge event: {event_type}")
            
    except Exception as e:
        logger.error(f"Failed to emit EventBridge event: {str(e)}")

@tracer.capture_method
def schedule_auto_remediation(anomaly_data: Dict[str, Any]) -> None:
    """Schedule auto-remediation action via SQS"""
    try:
        config = get_config()
        
        if config.dry_run or not config.auto_remediation_enabled:
            logger.info(f"Auto-remediation disabled or dry run mode for {anomaly_data.get('anomaly_id')}")
            return
        
        # Calculate execution time
        execute_at = datetime.now(timezone.utc) + timedelta(minutes=config.grace_period_minutes)
        
        # Prepare message
        message = {
            'action': 'auto_remediation',
            'anomaly_data': anomaly_data,
            'execute_at': execute_at.isoformat(),
            'scheduled_at': datetime.now(timezone.utc).isoformat(),
            'environment': ENVIRONMENT
        }
        
        # Calculate delay in seconds (max 15 minutes for SQS)
        delay_seconds = min(config.grace_period_minutes * 60, 900)
        
        response = sqs.send_message(
            QueueUrl=PROCESSING_QUEUE_URL,
            MessageBody=json.dumps(message),
            DelaySeconds=delay_seconds,
            MessageAttributes={
                'Action': {
                    'DataType': 'String',
                    'StringValue': 'auto_remediation'
                },
                'Environment': {
                    'DataType': 'String',
                    'StringValue': ENVIRONMENT
                },
                'AnomalyType': {
                    'DataType': 'String',
                    'StringValue': anomaly_data.get('model_type', 'unknown')
                }
            }
        )
        
        logger.info(f"Scheduled auto-remediation for {execute_at.isoformat()}, MessageId: {response['MessageId']}")
        
        # Update DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        table.update_item(
            Key={'anomaly_id': anomaly_data.get('anomaly_id')},
            UpdateExpression='SET auto_remediation_scheduled = :scheduled, '
                            'auto_remediation_time = :time, '
                            '#s = :status',
            ExpressionAttributeNames={
                '#s': 'status'
            },
            ExpressionAttributeValues={
                ':scheduled': True,
                ':time': execute_at.isoformat(),
                ':status': 'remediation_scheduled'
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to schedule auto-remediation: {str(e)}")
        # Don't raise, continue with processing

@tracer.capture_method
def trigger_auto_remediation(anomaly_data: Dict[str, Any]) -> None:
    """Execute auto-remediation action"""
    try:
        config = get_config()

        instance_id = anomaly_data.get('instance_id')
        model_type = anomaly_data.get('model_type')
        anomaly_id = anomaly_data.get('anomaly_id')

        if not config.auto_remediation_enabled:
            logger.info(f"Auto-remediation disabled for {anomaly_id}")
            return

        current_record = _get_current_anomaly_record(anomaly_id)
        if not _anomaly_record_allows_remediation(current_record, model_type):
            return

        if not _instance_is_remediation_eligible(instance_id):
            table = dynamodb.Table(DYNAMODB_TABLE_NAME)
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET #s = :status, remediation_skip_reason = :reason, remediation_time = :time',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': 'remediation_skipped',
                    ':reason': 'instance_not_eligible',
                    ':time': datetime.now(timezone.utc).isoformat(),
                }
            )
            return

        if config.dry_run:
            logger.info(f"DRY RUN: Would trigger auto-remediation for {anomaly_id} on {instance_id}")
            return
        
        if model_type == 'cpu_anomaly':
            # Reboot EC2 instance directly (avoids SSM document type restrictions)
            ec2.reboot_instances(InstanceIds=[instance_id])
            action = "instance_reboot"
            command_id = "ec2-reboot"
            
        elif model_type == 'log_anomaly':
            # Restart Nginx container
            response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName='AWS-RunShellScript',
                Parameters={
                    'commands': [
                        'if systemctl is-active --quiet nginx; then sudo systemctl restart nginx; fi',
                        'if docker ps -a --filter "name=cloudhight-app" --format "{{.ID}}" | grep -q .; then docker restart $(docker ps -a --filter "name=cloudhight-app" --format "{{.ID}}"); fi'
                    ],
                    'workingDirectory': ['/']
                },
                Comment=f"Auto-remediation for Nginx log anomaly {anomaly_id}",
                TimeoutSeconds=300
            )
            action = "container_restart"
            command_id = response['Command']['CommandId']
            
        else:
            logger.warning(f"Unknown model type for auto-remediation: {model_type}")
            return
        
        logger.info(f"Triggered {action} for {instance_id}, CommandId: {command_id}")
        metrics.add_metric(name="AutoRemediationsTriggered", unit="Count", value=1)
        
        # Update DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        table.update_item(
            Key={'anomaly_id': anomaly_id},
            UpdateExpression='SET auto_remediation_triggered = :triggered, '
                            'remediation_action = :action, '
                            'ssm_command_id = :command_id, '
                            'remediation_time = :time, '
                            '#s = :status '
                            'ADD remediation_attempts :attempt',
            ExpressionAttributeNames={
                '#s': 'status'
            },
            ExpressionAttributeValues={
                ':triggered': True,
                ':action': action,
                ':command_id': command_id,
                ':time': datetime.now(timezone.utc).isoformat(),
                ':status': 'remediation_executed',
                ':attempt': 1
            }
        )
        
        # Send remediation notification
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[{ENVIRONMENT.upper()}] Auto-Remediation Executed - {instance_id}",
                Message=f"""
Auto-remediation has been executed for anomaly {anomaly_id}.

Instance: {instance_id}
Action: {action}
Command ID: {command_id}
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
Jira Ticket: {anomaly_data.get('jira_ticket_id', 'N/A')}

Please verify that the remediation was successful.
""",
                MessageAttributes={
                    'environment': {
                        'DataType': 'String',
                        'StringValue': ENVIRONMENT
                    },
                    'action_type': {
                        'DataType': 'String',
                        'StringValue': 'auto_remediation'
                    }
                }
            )
        except Exception as e:
            logger.warning(f"Failed to send remediation notification: {str(e)}")
        
    except Exception as e:
        logger.error(f"Auto-remediation failed for {anomaly_data.get('anomaly_id')}: {str(e)}")
        metrics.add_metric(name="AutoRemediationFailures", unit="Count", value=1)
        
        # Update DynamoDB with failure
        try:
            table = dynamodb.Table(DYNAMODB_TABLE_NAME)
            table.update_item(
                Key={'anomaly_id': anomaly_data.get('anomaly_id')},
                UpdateExpression='SET auto_remediation_failed = :failed, '
                                'remediation_error = :error, '
                                '#s = :status',
                ExpressionAttributeNames={
                    '#s': 'status'
                },
                ExpressionAttributeValues={
                    ':failed': True,
                    ':error': str(e),
                    ':status': 'remediation_failed'
                }
            )
        except Exception as db_error:
            logger.error(f"Failed to update DynamoDB with remediation failure: {db_error}")

@tracer.capture_method
def process_cpu_anomaly(instance_id: str, metrics_data: List[float], score: float) -> None:
    """Process CPU anomaly detection result"""
    try:
        config = get_config()
        
        # Initialize table variable at the beginning
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Safety check: if CPU is low, don't flag as anomaly even if score is high
        if metrics_data:
            avg_cpu = sum(metrics_data) / len(metrics_data)
            max_cpu = max(metrics_data) if metrics_data else 0.0
            
            logger.info(f"CPU Analysis - Instance: {instance_id}, Avg: {avg_cpu:.2f}%, Max: {max_cpu:.2f}%, Score: {score:.4f}, Threshold: {config.cpu_threshold}")
            
            # If actual CPU is below 5%, don't flag as anomaly regardless of score
            if max_cpu < 5.0:
                logger.debug(f"Ignoring anomaly: CPU {max_cpu:.2f}% is below operational threshold")
                return
        
        if score < config.cpu_threshold:
            logger.debug(f"CPU anomaly score {score} below threshold {config.cpu_threshold} for {instance_id}")
            return
        
        anomaly_data = {
            'anomaly_id': f"cpu-{instance_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
            'model_type': 'cpu_anomaly',
            'instance_id': instance_id,
            'inference_score': score,
            'threshold': config.cpu_threshold,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data_points': len(metrics_data),
            'data_summary': f"CPU metrics analyzed: {len(metrics_data)} data points",
            'metadata': {
                'metric_name': 'CPUUtilization',
                'metric_namespace': 'AWS/EC2',
                'monitoring_frequency': MONITORING_FREQUENCY
            }
        }
        
        # Store inference result
        anomaly_id = store_inference_result(anomaly_data)
        anomaly_data['anomaly_id'] = anomaly_id
        
        # Emit EventBridge event
        emit_eventbridge_event(anomaly_data, 'CPU Anomaly Detected')
        metrics.add_metric(name="CPUAnomaliesDetected", unit="Count", value=1)
        
        try:
            # Create Jira ticket
            jira_ticket_id = create_jira_ticket(anomaly_data)
            anomaly_data['jira_ticket_id'] = jira_ticket_id
            
            # Update DynamoDB with Jira info
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET jira_ticket_id = :ticket_id, #s = :status',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':ticket_id': jira_ticket_id,
                    ':status': 'jira_ticket_created'
                }
            )
            
            # Send notification
            send_team_notification(anomaly_data, jira_ticket_id)
            
            # Schedule auto-remediation
            schedule_auto_remediation(anomaly_data)
            
        except JiraIntegrationError as e:
            logger.error(f"Jira integration failed for CPU anomaly {anomaly_id}: {str(e)}")
            # Update DynamoDB with failure status
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET #s = :status, error_message = :error',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': 'jira_failed',
                    ':error': str(e)
                }
            )
            # Don't schedule auto-remediation if Jira fails
        
    except Exception as e:
        logger.error(f"Failed to process CPU anomaly for {instance_id}: {str(e)}")
        metrics.add_metric(name="CPUProcessingErrors", unit="Count", value=1)

@tracer.capture_method
def process_log_anomaly(instance_id: str, logs_data: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Process log anomaly detection result"""
    try:
        config = get_config()
        
        # Initialize table variable at the beginning
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)

        anomalous_lines = analysis.get('anomalous_lines', [])
        anomalous_line_count = int(analysis.get('anomalous_line_count', 0))
        threshold = float(analysis.get('threshold', config.log_threshold))
        avg_anomaly_score = float(analysis.get('avg_anomaly_score', 0.0))
        max_anomaly_score = float(analysis.get('max_anomaly_score', 0.0))
        top_anomalous_lines = analysis.get('top_anomalous_lines', [])
        decision_method = analysis.get('decision_method', 'count')

        logger.info(
            "Log anomaly decision - Instance: %s, threshold=%.4f, anomalous_lines=%s, "
            "avg_anomaly_score=%.4f, max_anomaly_score=%.4f, decision_method=%s",
            instance_id,
            threshold,
            anomalous_line_count,
            avg_anomaly_score,
            max_anomaly_score,
            decision_method,
        )

        if anomalous_line_count < LOG_MIN_ANOMALOUS_LINES:
            logger.debug(
                "Skipping log anomaly for %s: anomalous_lines=%s below minimum=%s",
                instance_id,
                anomalous_line_count,
                LOG_MIN_ANOMALOUS_LINES,
            )
            return

        error_patterns = []
        for log in logs_data[:10]:  # Check first 10 logs for patterns
            message = log.get('message', '')
            if 'error' in message.lower():
                error_patterns.append(message[:100])  # First 100 chars

        detection_signature = _build_log_detection_signature(top_anomalous_lines)
        recent_matches = get_recent_log_anomaly_history(
            instance_id,
            detection_signature,
            lookback_minutes=max(LOG_JIRA_SUPPRESSION_MINUTES, LOG_REPEAT_LOOKBACK_MINUTES)
        )
        repeated_detection = len(recent_matches) >= 1
        recent_open_jira = next(
            (
                item for item in recent_matches
                if item.get('jira_ticket_id') and
                item.get('status') in {'jira_ticket_created', 'remediation_scheduled', 'remediation_executed'} and
                (
                    _parse_iso_datetime(item.get('created_at') or item.get('timestamp')) or
                    datetime.now(timezone.utc)
                ) >= datetime.now(timezone.utc) - timedelta(minutes=LOG_JIRA_SUPPRESSION_MINUTES)
            ),
            None
        )
        should_create_jira = anomalous_line_count >= LOG_JIRA_MIN_ANOMALOUS_LINES or repeated_detection
        
        anomaly_data = {
            'anomaly_id': f"log-{instance_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
            'model_type': 'log_anomaly',
            'instance_id': instance_id,
            'inference_score': avg_anomaly_score,
            'threshold': threshold,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'log_count': len(logs_data),
            'data_summary': (
                f"Nginx logs analyzed: {len(logs_data)} log entries. "
                f"Anomalous lines: {anomalous_line_count}. "
                f"Top patterns: {', '.join(set(error_patterns))[:200]}..."
            ),
            'metadata': {
                'log_type': 'nginx_access_error',
                'error_patterns': error_patterns[:5],
                'monitoring_frequency': MONITORING_FREQUENCY,
                'detection_signature': detection_signature,
                'anomalous_line_count': anomalous_line_count,
                'avg_anomaly_score': avg_anomaly_score,
                'max_anomaly_score': max_anomaly_score,
                'decision_method': decision_method,
                'top_anomalous_lines': [
                    {
                        'score': float(item.get('score', 0.0)),
                        'threshold': float(item.get('threshold', threshold)),
                        'line': item.get('line', '')[:200],
                    }
                    for item in top_anomalous_lines
                ],
                'repeated_detection': repeated_detection,
                'should_create_jira': should_create_jira,
            }
        }
        
        # Store inference result
        anomaly_id = store_inference_result(anomaly_data)
        anomaly_data['anomaly_id'] = anomaly_id
        
        # Emit EventBridge event
        emit_eventbridge_event(anomaly_data, 'Log Anomaly Detected')
        metrics.add_metric(name="LogAnomaliesDetected", unit="Count", value=1)
        metrics.add_metric(name="LogAnomalousLines", unit="Count", value=anomalous_line_count)

        if not should_create_jira:
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET #s = :status',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':status': 'detected_no_ticket'}
            )
            logger.info(
                "Log anomaly detected for %s without Jira. anomalous_lines=%s, repeated_detection=%s",
                instance_id,
                anomalous_line_count,
                repeated_detection,
            )
            return

        if recent_open_jira:
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET #s = :status, suppressed_by = :suppressed_by',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': 'jira_suppressed',
                    ':suppressed_by': recent_open_jira.get('jira_ticket_id', '')
                }
            )
            logger.info(
                "Suppressing Jira creation for %s due to recent open ticket %s within %s minutes",
                instance_id,
                recent_open_jira.get('jira_ticket_id', ''),
                LOG_JIRA_SUPPRESSION_MINUTES,
            )
            return

        try:
            # Create Jira ticket
            jira_ticket_id = create_jira_ticket(anomaly_data)
            anomaly_data['jira_ticket_id'] = jira_ticket_id
            
            # Update DynamoDB with Jira info
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET jira_ticket_id = :ticket_id, #s = :status',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':ticket_id': jira_ticket_id,
                    ':status': 'jira_ticket_created'
                }
            )
            
            # Send notification
            send_team_notification(anomaly_data, jira_ticket_id)
            
            # Schedule auto-remediation
            schedule_auto_remediation(anomaly_data)
            
        except JiraIntegrationError as e:
            logger.error(f"Jira integration failed for log anomaly {anomaly_id}: {str(e)}")
            # Update DynamoDB with failure status
            table.update_item(
                Key={'anomaly_id': anomaly_id},
                UpdateExpression='SET #s = :status, error_message = :error',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': 'jira_failed',
                    ':error': str(e)
                }
            )
            # Don't schedule auto-remediation if Jira fails
        
    except Exception as e:
        logger.error(f"Failed to process log anomaly for {instance_id}: {str(e)}")
        metrics.add_metric(name="LogProcessingErrors", unit="Count", value=1)

@tracer.capture_method
def process_sqs_message(record: Dict[str, Any]) -> None:
    """Process a single SQS message"""
    try:
        message_body = json.loads(record['body'])
        message_id = record.get('messageId', 'unknown')
        receipt_handle = record.get('receiptHandle')
        
        logger.info(f"Processing SQS message {message_id}: {message_body.get('action', 'unknown')}")
        
        if message_body.get('action') == 'auto_remediation':
            anomaly_data = message_body.get('anomaly_data', {})
            execute_at = datetime.fromisoformat(message_body['execute_at'].replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            
            if current_time >= execute_at:
                trigger_auto_remediation(anomaly_data)
                
                # Delete message from queue
                sqs.delete_message(
                    QueueUrl=PROCESSING_QUEUE_URL,
                    ReceiptHandle=receipt_handle
                )
                
                logger.info(f"Processed auto-remediation for {anomaly_data.get('anomaly_id')}")
            else:
                # Not time yet, change visibility timeout
                remaining_seconds = max(1, int((execute_at - current_time).total_seconds()))
                sqs.change_message_visibility(
                    QueueUrl=PROCESSING_QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=min(remaining_seconds, 900)  # Max 15 minutes
                )
                logger.debug(f"Delayed processing for {remaining_seconds} seconds")
        
        else:
            logger.warning(f"Unknown action in SQS message: {message_body.get('action')}")
            # Delete unknown messages
            sqs.delete_message(
                QueueUrl=PROCESSING_QUEUE_URL,
                ReceiptHandle=receipt_handle
            )
            
    except Exception as e:
        logger.error(f"Failed to process SQS message: {str(e)}")
        # Message will go to DLQ after maxReceiveCount
        metrics.add_metric(name="SQSProcessingErrors", unit="Count", value=1)

@tracer.capture_method
def process_instance(instance_id: str) -> None:
    """Process a single EC2 instance for anomalies"""
    try:
        logger.info(f"Processing instance: {instance_id}")
        
        # CPU Anomaly Detection
        try:
            cpu_metrics = fetch_cpu_metrics(instance_id)
            if cpu_metrics:
                cpu_score = invoke_sagemaker_model(
                    CPU_MODEL_ENDPOINT,
                    {'data': cpu_metrics, 'instance_id': instance_id}
                )
                process_cpu_anomaly(instance_id, cpu_metrics, cpu_score)
            else:
                logger.debug(f"No CPU metrics available for {instance_id}")
        except Exception as e:
            logger.error(f"CPU anomaly detection failed for {instance_id}: {str(e)}")
            metrics.add_metric(name="CPUDetectionErrors", unit="Count", value=1)
        
        # Log Anomaly Detection
        try:
            nginx_logs = fetch_nginx_logs(instance_id)
            if nginx_logs:
                recent_logs = sorted(
                    nginx_logs,
                    key=lambda log: log.get('timestamp', 0),
                    reverse=True
                )[:50]
                log_lines = [log.get('message', '') for log in recent_logs if log.get('message')]
                log_analysis = invoke_sagemaker_log_model(
                    LOG_MODEL_ENDPOINT,
                    log_lines
                )
                process_log_anomaly(instance_id, recent_logs, log_analysis)
            else:
                logger.debug(f"No Nginx logs available for {instance_id}")
        except Exception as e:
            logger.error(f"Log anomaly detection failed for {instance_id}: {str(e)}")
            metrics.add_metric(name="LogDetectionErrors", unit="Count", value=1)
        
    except Exception as e:
        logger.error(f"Failed to process instance {instance_id}: {str(e)}")
        metrics.add_metric(name="InstanceProcessingErrors", unit="Count", value=1)

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Main Lambda handler"""
    try:
        logger.info(f"Starting anomaly detection in {ENVIRONMENT} environment")
        logger.debug(f"Event: {json.dumps(event, default=str)}")
        
        # Add cold start metric
        if context:
            metrics.add_metadata(key="function_version", value=context.function_version)
            metrics.add_metadata(key="function_name", value=context.function_name)
        
        # Check if this is an SQS event
        if 'Records' in event and event['Records'] and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:sqs':
            logger.info(f"Processing {len(event['Records'])} SQS messages")
            
            for record in event['Records']:
                try:
                    process_sqs_message(record)
                except Exception as e:
                    logger.error(f"Failed to process SQS record: {str(e)}")
                    continue
            
            return {
                'statusCode': 200,
                'body': json.dumps({'processed': len(event['Records'])})
            }
        
        # Scheduled execution - process instances
        config = get_config()
        logger.info(f"Loaded config: CPU threshold={config.cpu_threshold}, "
                   f"Log threshold={config.log_threshold}, "
                   f"Grace period={config.grace_period_minutes} minutes, "
                   f"Auto-remediation={'Enabled' if config.auto_remediation_enabled else 'Disabled'}, "
                   f"Dry run={'Yes' if config.dry_run else 'No'}")
        
        # Get instances to monitor
        instances = get_instances_to_monitor()
        
        if not instances:
            logger.warning("No instances found to monitor")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No instances to monitor'})
            }
        
        logger.info(f"Monitoring {len(instances)} instances")
        metrics.add_metric(name="InstancesMonitored", unit="Count", value=len(instances))
        
        # Process each instance
        for instance_id in instances:
            try:
                process_instance(instance_id)
            except Exception as e:
                logger.error(f"Failed to process instance {instance_id}: {str(e)}")
                continue
        
        logger.info("Anomaly detection completed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Anomaly detection completed',
                'instances_processed': len(instances),
                'environment': ENVIRONMENT,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda handler failed: {str(e)}")
        metrics.add_metric(name="LambdaHandlerErrors", unit="Count", value=1)
        
        # Send error notification
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[{ENVIRONMENT.upper()}] Anomaly Detection System Error",
                Message=f"""
Anomaly Detection System encountered an error:

Error: {str(e)}
Environment: {ENVIRONMENT}
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

Please check CloudWatch logs for details.
"""
            )
        except Exception as sns_error:
            logger.error(f"Failed to send error notification: {sns_error}")
        
        raise

# Local testing
if __name__ == "__main__":
    # Test event for local development
    test_event = {
        "Records": [
            {
                "messageId": "test-message-id",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "action": "auto_remediation",
                    "anomaly_data": {
                        "anomaly_id": "test-anomaly",
                        "instance_id": "i-1234567890abcdef0",
                        "model_type": "cpu_anomaly",
                        "inference_score": 0.95
                    },
                    "execute_at": datetime.now(timezone.utc).isoformat()
                })
            }
        ]
    }
    
    # Override environment for local testing
    os.environ['ENVIRONMENT'] = 'dev'
    os.environ['DYNAMODB_TABLE'] = 'anomaly-results-dev'
    os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:anomaly-notifications-dev'
    os.environ['CPU_MODEL_ENDPOINT'] = 'cpu-anomaly-detector-prod'
    os.environ['LOG_MODEL_ENDPOINT'] = 'nginx-anomaly-detector-prod'
    os.environ['JIRA_PROJECT_KEY'] = 'AIOP'
    
    # Test handler
    result = lambda_handler(test_event, None)
    print(f"Test result: {result}")
