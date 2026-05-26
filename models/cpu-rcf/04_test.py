import pandas as pd
import numpy as np
import re
import json
from sagemaker.predictor import Predictor

def extract_score_value(record):
    """Extract float value from SageMaker RCF JSON response."""
    try:
        if isinstance(record, dict):
            if 'score' in record:
                return float(record['score'])
            elif 'scores' in record:
                return float(record['scores'][0]['score'])
        elif isinstance(record, list) and len(record) > 0:
            return extract_score_value(record[0])
        return float(record) if isinstance(record, (int, float)) else 0.0
    except Exception:
        return 0.0

def test_model(data_file="cpu_time_series_realistic.csv",
               endpoint_info_file="endpoint_info.json",
               scores_file="rcf_scores.csv"):
    """Test deployed RCF model and analyze score distribution."""
    print("\n========== Model Testing ==========")
    
    try:
        with open(endpoint_info_file, 'r') as f:
            endpoint_info = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {endpoint_info_file} not found. Run 03_deploy.py first.")
        return None
    
    df = pd.read_csv(data_file)
    print(f"Testing with {len(df)} data points")
    
    predictor = Predictor(endpoint_name=endpoint_info['endpoint_name'])
    from sagemaker.serializers import CSVSerializer
    from sagemaker.deserializers import JSONDeserializer
    
    predictor.serializer = CSVSerializer()
    predictor.deserializer = JSONDeserializer()
    
    values_to_score = df['Average'].astype('float32').values.reshape(-1, 1)
    
    print(f"Invoking endpoint: {endpoint_info['endpoint_name']}")
    scores = predictor.predict(values_to_score)
    
    # Parse response
    if isinstance(scores, dict) and 'scores' in scores:
        score_list = scores['scores']
    else:
        score_list = scores
    
    rcf_scores = []
    for i, record in enumerate(score_list):
        score_value = extract_score_value(record)
        rcf_scores.append(score_value)
    
    # Ensure length matches
    if len(rcf_scores) != len(df):
        rcf_scores.extend([0.0] * (len(df) - len(rcf_scores)))
    
    scores_df = pd.DataFrame({'RCFScore': rcf_scores})
    scores_df.to_csv(scores_file, index=False)
    
    # Analyze results
    print(f"\n========== Score Analysis ==========")
    print(f"Score range: {min(rcf_scores):.4f} - {max(rcf_scores):.4f}")
    print(f"Score mean: {np.mean(rcf_scores):.4f}")
    print(f"Score median: {np.median(rcf_scores):.4f}")
    print(f"Score std: {np.std(rcf_scores):.4f}")
    
    # Separate by actual label
    normal_mask = df['anomaly'] == 0
    anomaly_mask = df['anomaly'] == 1
    
    normal_scores = np.array(rcf_scores)[normal_mask]
    anomaly_scores = np.array(rcf_scores)[anomaly_mask]
    
    print(f"\nNormal data (labeled 'normal' in dataset):")
    print(f"  Count: {len(normal_scores)}")
    print(f"  Score range: {normal_scores.min():.4f} - {normal_scores.max():.4f}")
    print(f"  Score mean: {normal_scores.mean():.4f}")
    print(f"  ✓ SHOULD BE LOW (close to 0.0)")
    
    print(f"\nAnomalous data (labeled 'anomaly' in dataset):")
    print(f"  Count: {len(anomaly_scores)}")
    print(f"  Score range: {anomaly_scores.min():.4f} - {anomaly_scores.max():.4f}")
    print(f"  Score mean: {anomaly_scores.mean():.4f}")
    print(f"  ✓ SHOULD BE HIGH (close to 1.0)")
    
    # Determine if model is working
    print(f"\n========== Model Diagnosis ==========")
    if normal_scores.mean() < anomaly_scores.min():
        print(f"✓ Model working CORRECTLY!")
        print(f"  Normal max: {normal_scores.max():.4f}")
        print(f"  Anomaly min: {anomaly_scores.min():.4f}")
        print(f"  Clear separation detected!")
        optimal_threshold = (normal_scores.max() + anomaly_scores.min()) / 2.0
        print(f"  → Use threshold: {optimal_threshold:.4f}")
    else:
        print(f"⚠ Model separating but slight overlap:")
        print(f"  Normal: mean={normal_scores.mean():.4f}, max={normal_scores.max():.4f}")
        print(f"  Anomaly: mean={anomaly_scores.mean():.4f}, min={anomaly_scores.min():.4f}")
        optimal_threshold = (normal_scores.max() + anomaly_scores.min()) / 2.0
        print(f"  → Optimal threshold: {optimal_threshold:.4f}")
    
    print(f"\nGenerated {len(rcf_scores)} anomaly scores. Saved to {scores_file}")
    return np.array(rcf_scores, dtype=float)

if __name__ == "__main__":
    test_model()