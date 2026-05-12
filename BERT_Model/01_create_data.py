import argparse
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None


RANDOM_SEED = 42
random.seed(RANDOM_SEED)


ACCESS_NORMAL_STATUSES = [200, 204, 206, 301, 302, 304, 404]
ACCESS_ANOMALY_STATUSES = [401, 403, 429, 499, 500, 502, 503, 504]
NORMAL_USER_AGENTS = [
    "Mozilla/5.0",
    "curl/8.5.0",
    "ELB-HealthChecker/2.0",
    "kube-probe/1.29",
    "Amazon-Route53-Health-Check-Service",
]
NORMAL_PATHS = [
    "/",
    "/index.html",
    "/health",
    "/status",
    "/static/app.js",
    "/api/items",
    "/api/orders",
    "/login",
    "/assets/logo.png",
]
ANOMALOUS_PATHS = [
    "/api/checkout",
    "/api/payments",
    "/admin",
    "/wp-login.php",
    "/api/internal/report",
    "/auth/token",
]
NORMAL_MESSAGES = [
    "client sent HTTP/1.1 request without Host header",
    "connection closed while reading upstream",
    "request timed out while reading client request body",
    "upstream response is buffered to a temporary file",
    "epoll_wait() reported that client prematurely closed connection",
]
ANOMALY_MESSAGES = [
    "upstream server temporarily disabled while connecting to upstream",
    "connect() failed (111: Connection refused) while connecting to upstream",
    "no live upstreams while connecting to upstream",
    "upstream timed out (110: Connection timed out) while reading response header from upstream",
    "recv() failed (104: Connection reset by peer) while reading response header from upstream",
    "limiting requests, excess burst from client",
]
ANOMALY_KEYWORDS = (
    " 499 ",
    " 500 ",
    " 502 ",
    " 503 ",
    " 504 ",
    "[error]",
    "[crit]",
    "temporarily disabled",
    "connection refused",
    "no live upstreams",
    "timed out",
    "reset by peer",
    "excess burst",
)
ID_PATTERN = re.compile(r"[A-Fa-f0-9]{8,32}")


@dataclass
class Sample:
    text: str
    label: int
    source: str
    difficulty: str


def random_ip() -> str:
    return ".".join(str(random.randint(1, 255)) for _ in range(4))


def random_trace_id() -> str:
    return "".join(random.choices("0123456789abcdef", k=16))


def random_timestamp() -> str:
    now = datetime.now(timezone.utc)
    ts = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
    return ts.strftime("%d/%b/%Y:%H:%M:%S +0000")


def random_error_timestamp() -> str:
    now = datetime.now(timezone.utc)
    ts = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
    return ts.strftime("%Y/%m/%d %H:%M:%S")


def generate_access_log(status: int, path: str, user_agent: str, bytes_sent: int, latency_ms: int) -> str:
    ip = random_ip()
    request_id = random_trace_id()
    timestamp = random_timestamp()
    method = random.choice(["GET", "POST", "PUT"])
    referrer = random.choice(["-", "https://example.com", "https://portal.internal"])
    return (
        f'{ip} - - [{timestamp}] "{method} {path} HTTP/1.1" {status} {bytes_sent} '
        f'"{referrer}" "{user_agent}" rt={latency_ms/1000:.3f} req_id={request_id}'
    )


def generate_error_log(level: str, message: str) -> str:
    return f"{random_error_timestamp()} [{level}] [client {random_ip()}] {message} request_id={random_trace_id()}"


def normalize_log(line: str) -> str:
    line = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<IP>", line)
    line = re.sub(r"\[\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} \+\d{4}\]", "[<TIME>]", line)
    line = re.sub(r"\b\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\b", "<TIME>", line)
    line = re.sub(r"req_id=[A-Fa-f0-9]+", "req_id=<ID>", line)
    line = ID_PATTERN.sub("<ID>", line)
    line = re.sub(r"\brt=\d+\.\d+\b", "rt=<FLOAT>", line)
    line = re.sub(r"\b\d+\b", "<NUM>", line)
    return re.sub(r"\s+", " ", line).strip()


def label_line(line: str) -> int:
    lowered = line.lower()
    return int(any(keyword in lowered for keyword in ANOMALY_KEYWORDS))


def build_normal_samples(count: int) -> List[Sample]:
    samples: List[Sample] = []
    for _ in range(count):
        sample_type = random.choice(["access", "error", "hard_negative"])
        if sample_type == "access":
            status = random.choices(ACCESS_NORMAL_STATUSES, weights=[45, 5, 5, 10, 10, 5, 20])[0]
            line = generate_access_log(
                status=status,
                path=random.choice(NORMAL_PATHS),
                user_agent=random.choice(NORMAL_USER_AGENTS),
                bytes_sent=random.randint(300, 12000),
                latency_ms=random.randint(5, 800),
            )
            difficulty = "standard"
        elif sample_type == "hard_negative":
            line = generate_access_log(
                status=random.choice([404, 429]),
                path=random.choice(NORMAL_PATHS + ANOMALOUS_PATHS),
                user_agent=random.choice(NORMAL_USER_AGENTS + ["python-requests/2.31"]),
                bytes_sent=random.randint(0, 4000),
                latency_ms=random.randint(200, 2000),
            )
            difficulty = "hard_negative"
        else:
            line = generate_error_log(
                level=random.choice(["warn", "notice", "info"]),
                message=random.choice(NORMAL_MESSAGES),
            )
            difficulty = "standard"

        samples.append(
            Sample(
                text=normalize_log(line),
                label=0,
                source=sample_type,
                difficulty=difficulty,
            )
        )
    return samples


def build_anomaly_samples(count: int) -> List[Sample]:
    samples: List[Sample] = []
    for _ in range(count):
        sample_type = random.choice(["access", "error", "burst"])
        if sample_type == "access":
            line = generate_access_log(
                status=random.choice(ACCESS_ANOMALY_STATUSES),
                path=random.choice(ANOMALOUS_PATHS),
                user_agent=random.choice(NORMAL_USER_AGENTS + ["sqlmap/1.7", "Nmap Scripting Engine"]),
                bytes_sent=random.randint(0, 2500),
                latency_ms=random.randint(900, 8000),
            )
        elif sample_type == "burst":
            base = generate_access_log(
                status=random.choice([499, 500, 502, 503, 504]),
                path=random.choice(ANOMALOUS_PATHS),
                user_agent="Mozilla/5.0",
                bytes_sent=random.randint(0, 1024),
                latency_ms=random.randint(1200, 9000),
            )
            line = f"{base} upstream_error=retry_exhausted circuit=open"
        else:
            line = generate_error_log(
                level=random.choice(["error", "crit"]),
                message=random.choice(ANOMALY_MESSAGES),
            )

        samples.append(
            Sample(
                text=normalize_log(line),
                label=1,
                source=sample_type,
                difficulty="standard",
            )
        )
    return samples


def build_context_windows(
    normal_samples: Sequence[Sample],
    anomaly_samples: Sequence[Sample],
    count: int,
    min_window: int = 3,
    max_window: int = 6,
) -> List[Sample]:
    windows: List[Sample] = []
    for _ in range(count):
        window_size = random.randint(min_window, max_window)
        is_anomaly = random.random() < 0.45
        lines: List[Sample] = []

        if is_anomaly:
            anomaly_count = random.randint(1, max(1, window_size // 2))
            lines.extend(random.sample(list(anomaly_samples), k=anomaly_count))
            lines.extend(random.sample(list(normal_samples), k=window_size - anomaly_count))
        else:
            lines.extend(random.sample(list(normal_samples), k=window_size))

        random.shuffle(lines)
        text = " [SEP] ".join(sample.text for sample in lines)
        label = int(any(sample.label == 1 for sample in lines))
        difficulty = "context_hard_negative" if label == 0 and any(s.difficulty == "hard_negative" for s in lines) else "context"
        windows.append(Sample(text=text, label=label, source="context_window", difficulty=difficulty))
    return windows


def to_records(samples: Sequence[Sample]) -> List[Dict[str, str]]:
    return [
        {
            "text": sample.text,
            "label": sample.label,
            "source": sample.source,
            "difficulty": sample.difficulty,
        }
        for sample in samples
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def upload_directory_to_s3(local_root: Path, bucket: str, prefix: str) -> None:
    if boto3 is None:
        raise ImportError("boto3 is required for S3 upload. Install boto3 or omit --bucket/--s3-prefix.")
    s3 = boto3.client("s3")
    for file_path in local_root.rglob("*.json"):
        relative = file_path.relative_to(local_root).as_posix()
        key = f"{prefix.rstrip('/')}/{relative}"
        s3.upload_file(str(file_path), bucket, key)
        print(f"[INFO] Uploaded {file_path} to s3://{bucket}/{key}")


def stratified_split(records: Sequence[Dict[str, Any]], train_ratio: float, validation_ratio: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[int(record["label"])].append(record)

    train_records: List[Dict[str, Any]] = []
    validation_records: List[Dict[str, Any]] = []
    test_records: List[Dict[str, Any]] = []

    for group in grouped.values():
        random.shuffle(group)
        total = len(group)
        train_end = int(total * train_ratio)
        validation_end = train_end + int(total * validation_ratio)
        train_records.extend(group[:train_end])
        validation_records.extend(group[train_end:validation_end])
        test_records.extend(group[validation_end:])

    random.shuffle(train_records)
    random.shuffle(validation_records)
    random.shuffle(test_records)
    return train_records, validation_records, test_records


def create_dataset(output_dir: Path, bucket: str = "", s3_prefix: str = "") -> Dict[str, int]:
    normal_base = build_normal_samples(4000)
    anomaly_base = build_anomaly_samples(1400)
    context_samples = build_context_windows(normal_base, anomaly_base, count=2200)

    all_samples = normal_base + anomaly_base + context_samples
    records = to_records(all_samples)
    labels = [record["label"] for record in records]
    train_records, val_records, test_records = stratified_split(records, train_ratio=0.8, validation_ratio=0.1)

    write_json(output_dir / "train" / "train.json", train_records)
    write_json(output_dir / "validation" / "validation.json", val_records)
    write_json(output_dir / "test" / "test.json", test_records)
    write_json(
        output_dir / "dataset_summary.json",
        {
            "counts": {
                "train": len(train_records),
                "validation": len(val_records),
                "test": len(test_records),
            },
            "label_distribution": dict(Counter(labels)),
            "notes": [
                "Logs are normalized before training.",
                "Samples include hard negatives and context windows.",
            ],
        },
    )

    if bucket and s3_prefix:
        upload_directory_to_s3(output_dir, bucket, s3_prefix)

    return {
        "train": len(train_records),
        "validation": len(val_records),
        "test": len(test_records),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="BERT_UPDATE/data")
    parser.add_argument("--bucket", default="")
    parser.add_argument("--s3-prefix", default="")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    counts = create_dataset(Path(args.output_dir), bucket=args.bucket, s3_prefix=args.s3_prefix)
    print(f"[INFO] Dataset created: {counts}")
