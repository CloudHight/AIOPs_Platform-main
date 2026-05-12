import pandas as pd
from sagemaker import RandomCutForest, get_execution_role
import json

def train_model(input_file="cpu_time_series_realistic.csv",
                model_info_file="model_info.json"):
    """Train Random Cut Forest model optimized for CPU anomaly detection.
    
    Data distribution (from 01_create.py):
    - Normal: Gaussian around 5% CPU ± 3% (95% of data)
    - Anomalous: Gaussian around 92% CPU ± 4% (5% of data)
    
    RCF will learn to detect when CPU is in the "normal zone" (0-20%)
    and flag anything deviating significantly or in the "anomaly zone" (85-100%)
    """
    print("\n========== Training Random Cut Forest ==========")
    
    df = pd.read_csv(input_file)
    if df.empty or 'Average' not in df:
        print("ERROR: No valid data for model training.")
        return None
    
    train_values = df['Average'].dropna().values.reshape(-1, 1)
    n_points = len(train_values)
    
    print(f"Dataset: {n_points} records")
    print(f"Value range: {train_values.min():.2f}% - {train_values.max():.2f}%")
    print(f"\nHyperparameters:")
    print(f"  - num_trees: 100 (more trees = better anomaly detection)")
    print(f"  - num_samples_per_tree: 256 (standard for RCF)")
    print(f"  - feature_dim: 1 (single CPU metric)")
    print(f"\nStarting training...\n")
    
    rcf = RandomCutForest(
        role=get_execution_role(),
        instance_count=1,
        instance_type='ml.m5.large',
        num_trees=100,  # More trees for better detection of two distinct clusters
        num_samples_per_tree=256,  # Standard SageMaker RCF value
        eval_metrics=["accuracy", "precision_recall_fscore"],
        feature_dim=1
    )
    
    rcf.fit(rcf.record_set(train_values))
    
    print(f"✓ Training complete!")
    print(f"✓ Training job: {rcf.latest_training_job.name}")
    
    # Save model info
    model_info = {
        'training_job_name': rcf.latest_training_job.name
    }
    with open(model_info_file, 'w') as f:
        json.dump(model_info, f)
    
    print(f"Model training complete. Info saved to {model_info_file}")
    return rcf

if __name__ == "__main__":
    train_model()