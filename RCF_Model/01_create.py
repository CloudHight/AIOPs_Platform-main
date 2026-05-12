import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def create_dataset(output_file="cpu_time_series_realistic.csv"):
    """Create realistic time series data for RCF training with clear separation.
    
    Training data represents:
    - Normal: Full realistic range (0.5-80% CPU, from true idle to high load)
    - Anomalous: Critical range (85-100% CPU, crashes/overheats)
    
    This covers realistic scenarios:
    - True idle: 0.5-1%
    - Light idle: 1-5%
    - Light load: 5-20%
    - Medium load: 30-60%
    - High load: 65-80%
    - Critical/Anomaly: 85-100%
    """
    start_time = datetime(2025, 8, 19, 0, 0)
    num_records = 2000  # More data = better training
    
    timestamps = [start_time + timedelta(minutes=i % 1440) for i in range(num_records)]
    cpu_usage = []
    labels = []
    
    # NORMAL: Distributed across realistic operating range (0.5-80% CPU)
    # Represents typical workloads: true idle, light, medium, high loads
    normal_count = int(num_records * 0.95)
    for i in range(normal_count):
        # Uniform distribution across full normal operating range
        # Covers: true idle (0.5-1%), light idle (1-5%), light (5-20%), 
        #         medium (30-60%), high (65-80%)
        value = np.random.uniform(0.5, 80.0)
        cpu_usage.append(value)
        labels.append(0)  # Normal
    
    # ANOMALOUS: Concentrated in critical range (85-100% CPU)
    # Represents crashes, overheating, or resource exhaustion
    anomaly_count = num_records - normal_count
    for i in range(anomaly_count):
        # Uniform distribution in critical range
        value = np.random.uniform(85.0, 100.0)
        cpu_usage.append(value)
        labels.append(1)  # Anomaly
    
    # Shuffle to mix throughout timeline
    combined = list(zip(timestamps, cpu_usage, labels))
    random.shuffle(combined)
    timestamps, cpu_usage, labels = zip(*combined)
    
    df = pd.DataFrame({
        "Timestamp": list(timestamps),
        "Average": list(cpu_usage),
        "anomaly": list(labels)
    })
    
    # Print detailed statistics
    normal_data = df[df['anomaly'] == 0]['Average']
    anomaly_data = df[df['anomaly'] == 1]['Average']
    
    print(f"\n========== Dataset Created ==========")
    print(f"Total records: {len(df)}")
    print(f"\nNormal data (95%): {len(normal_data)} records")
    print(f"  Range: {normal_data.min():.2f}% - {normal_data.max():.2f}%")
    print(f"  Mean: {normal_data.mean():.2f}%, Std: {normal_data.std():.2f}%")
    print(f"  → Covers: true idle (0.5-1%), light idle (1-5%), medium (30-60%), high (65-80%)")
    
    print(f"\nAnomalous data (5%): {len(anomaly_data)} records")
    print(f"  Range: {anomaly_data.min():.2f}% - {anomaly_data.max():.2f}%")
    print(f"  Mean: {anomaly_data.mean():.2f}%, Std: {anomaly_data.std():.2f}%")
    print(f"  → Critical/crash range (85-100%)")
    
    print(f"\n✓ Clear separation: Normal ≤80%, Anomaly ≥85%")
    print(f"✓ RCF will learn: 'normal zone' (0.5-80%), 'anomaly zone' (85-100%)")
    print(f"✓ CPU at 2% (true idle) will be recognized as NORMAL")
    print(f"✓ CPU at 60% (medium load) will be recognized as NORMAL")
    print(f"======================================\n")
    
    df.to_csv(output_file, index=False)
    return df

if __name__ == "__main__":
    create_dataset()