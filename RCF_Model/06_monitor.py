import pandas as pd
import numpy as np

def analyze_anomalies(data_file="cpu_time_series_realistic.csv",
                      scores_file="rcf_scores.csv",
                      threshold_score=0.50):
    """Analyze RCF anomaly detection results."""
    print("\n========== Anomaly Analysis ==========")
    
    df = pd.read_csv(data_file)
    scores_df = pd.read_csv(scores_file)
    
    df['RCFScore'] = scores_df['RCFScore']
    
    # Separate by RCF score threshold
    df['RCFAnomaly'] = (df['RCFScore'] > threshold_score).astype(int)
    
    print(f"Using RCF threshold: {threshold_score}")
    print(f"Instances with RCF score > {threshold_score}: {(df['RCFAnomaly'] == 1).sum()}")
    
    # Compare to ground truth labels
    print(f"\nGround Truth (from dataset labels):")
    print(f"  Normal instances: {(df['anomaly'] == 0).sum()}")
    print(f"  Anomalous instances: {(df['anomaly'] == 1).sum()}")
    
    print(f"\nRCF Detection (score > {threshold_score}):")
    print(f"  Detected normal: {((df['anomaly'] == 0) & (df['RCFAnomaly'] == 0)).sum()}")
    print(f"  Detected anomaly: {((df['anomaly'] == 1) & (df['RCFAnomaly'] == 1)).sum()}")
    print(f"  False positives: {((df['anomaly'] == 0) & (df['RCFAnomaly'] == 1)).sum()}")
    print(f"  False negatives: {((df['anomaly'] == 1) & (df['RCFAnomaly'] == 0)).sum()}")
    
    # Show distribution
    print(f"\nRCF Score Statistics:")
    print(f"  Mean: {df['RCFScore'].mean():.4f}")
    print(f"  Median: {df['RCFScore'].median():.4f}")
    print(f"  Std Dev: {df['RCFScore'].std():.4f}")
    print(f"  Min: {df['RCFScore'].min():.4f}")
    print(f"  Max: {df['RCFScore'].max():.4f}")
    
    # Show sample detections
    detected = df[df['RCFAnomaly'] == 1].sort_values('RCFScore', ascending=False)
    if len(detected) > 0:
        print(f"\nTop detected anomalies:")
        print(detected[['Timestamp', 'Average', 'anomaly', 'RCFScore']].head(10).to_string())
    
    # Save analyzed data
    df.to_csv("analyzed_results.csv", index=False)
    print(f"\n✓ Results saved to analyzed_results.csv")
    
    # Save analyzed data
    df.to_csv("analyzed_results.csv", index=False)
    return df

def monitor_performance(df):
    """Monitor model performance metrics."""
    print("========== Performance Monitoring ==========")
    
    print(f"Dataset size: {len(df)}")
    print(f"Average CPU usage: {df['Average'].mean():.2f}")
    print(f"CPU usage std: {df['Average'].std():.2f}")
    print(f"RCF score range: {df['RCFScore'].min():.4f} - {df['RCFScore'].max():.4f}")
    
    # Basic drift detection
    recent_data = df.tail(len(df)//4)  # Last 25% of data
    historical_mean = df.head(len(df)//2)['Average'].mean()
    recent_mean = recent_data['Average'].mean()
    
    drift = abs(recent_mean - historical_mean) / historical_mean
    print(f"Data drift indicator: {drift:.4f}")
    
    if drift > 0.1:
        print("WARNING: Significant data drift detected")

if __name__ == "__main__":
    df_analyzed = analyze_anomalies()
    monitor_performance(df_analyzed)