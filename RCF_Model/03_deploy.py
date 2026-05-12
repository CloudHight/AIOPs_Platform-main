import json
from sagemaker import RandomCutForest

def deploy_model(model_info_file="model_info.json",
                 endpoint_info_file="endpoint_info.json",
                 instance_count=1,
                 instance_type="ml.t2.medium",
                 endpoint_name="cpu-anomaly-detector-prod"):
    """Deploy the trained model to a SageMaker endpoint."""
    print("========== Model Deployment ==========")
    
    # Load model info
    with open(model_info_file, 'r') as f:
        model_info = json.load(f)
    
    # Attach to existing model
    rcf = RandomCutForest.attach(model_info['training_job_name'])
    
    predictor = rcf.deploy(
        initial_instance_count=instance_count,
        instance_type=instance_type,
        endpoint_name=endpoint_name
    )
    
    # Save endpoint info
    endpoint_info = {'endpoint_name': predictor.endpoint_name}
    with open(endpoint_info_file, 'w') as f:
        json.dump(endpoint_info, f)
    
    print(f"Model deployed to endpoint: {predictor.endpoint_name}")
    print(f"Endpoint info saved to {endpoint_info_file}")
    return predictor

def cleanup_endpoint(endpoint_info_file="endpoint_info.json"):
    """Clean up the deployed endpoint to avoid charges."""
    try:
        import boto3
        with open(endpoint_info_file, 'r') as f:
            endpoint_info = json.load(f)
        
        client = boto3.client('sagemaker')
        client.delete_endpoint(EndpointName=endpoint_info['endpoint_name'])
        print("Endpoint deleted successfully")
    except Exception as e:
        print(f"Error deleting endpoint: {e}")

if __name__ == "__main__":
    predictor = deploy_model(endpoint_name="cpu-anomaly-detector-prod")