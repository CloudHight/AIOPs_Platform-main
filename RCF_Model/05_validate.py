import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

def validate_model(data_file="cpu_time_series_realistic.csv",
                   scores_file="rcf_scores.csv"):
    """Validate model performance and find optimal threshold."""
    print("\n========== Model Validation ==========")
    
    df = pd.read_csv(data_file)
    scores_df = pd.read_csv(scores_file)
    rcf_scores = scores_df['RCFScore'].values
    
    # Separate scores by actual label
    normal_scores = rcf_scores[df['anomaly'] == 0]
    anomaly_scores = rcf_scores[df['anomaly'] == 1]
    
    print(f"\nScore Statistics:")
    print(f"Normal data:    mean={normal_scores.mean():.4f}, std={normal_scores.std():.4f}")
    print(f"                min={normal_scores.min():.4f}, max={normal_scores.max():.4f}")
    print(f"Anomaly data:   mean={anomaly_scores.mean():.4f}, std={anomaly_scores.std():.4f}")
    print(f"                min={anomaly_scores.min():.4f}, max={anomaly_scores.max():.4f}")
    
    # Find optimal threshold (midpoint between normal and anomaly distributions)
    threshold = (normal_scores.max() + anomaly_scores.min()) / 2.0
    print(f"\n✓ Optimal threshold: {threshold:.4f}")
    print(f"  (Separates normal max {normal_scores.max():.4f} from anomaly min {anomaly_scores.min():.4f})")
    
    # Make predictions using optimal threshold
    predictions = (rcf_scores > threshold).astype(int)
    
    # Calculate metrics
    accuracy = accuracy_score(df['anomaly'], predictions)
    precision = precision_score(df['anomaly'], predictions, zero_division=0)
    recall = recall_score(df['anomaly'], predictions, zero_division=0)
    f1 = f1_score(df['anomaly'], predictions, zero_division=0)
    
    print(f"\nPerformance Metrics:")
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    
    # Diagnosis
    print(f"\n========== Diagnosis ==========")
    if normal_scores.mean() < 0.3 and anomaly_scores.mean() > 0.7:
        print(f"✓ Model working CORRECTLY")
        print(f"  Normal scores: {normal_scores.mean():.4f} (< 0.3) ✓")
        print(f"  Anomaly scores: {anomaly_scores.mean():.4f} (> 0.7) ✓")
        print(f"  Clear separation detected!")
    else:
        print(f"✗ Model may have issues")
        print(f"  Expected: Normal <0.3, Anomaly >0.7")
        print(f"  Got: Normal {normal_scores.mean():.4f}, Anomaly {anomaly_scores.mean():.4f}")
    
    results = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'threshold': threshold,
        'normal_mean': normal_scores.mean(),
        'anomaly_mean': anomaly_scores.mean()
    }
    
    # Save validation results
    pd.DataFrame([results]).to_csv("validation_results.csv", index=False)
    print(f"\n✓ Results saved to validation_results.csv")
    return results

if __name__ == "__main__":
    validate_model()