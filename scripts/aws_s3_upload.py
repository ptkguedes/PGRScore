"""S3 ingest simulation: raw prefix -> Python process -> processed prefix.

Local fallback (no AWS credentials): treat directories as buckets.

  data/raw          ~ s3://pgrscore-raw/
  output/           ~ s3://pgrscore-processed/
  SQLite            ~ DynamoDB item store for dashboard queries

Lambda-style handler processes an ObjectCreated event. Glue would run the
same ``pipeline.run.run`` as a job script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.run import run  # noqa: E402

DEFAULT_RAW_BUCKET = "pgrscore-raw"
DEFAULT_PROCESSED_BUCKET = "pgrscore-processed"


def _client():
    try:
        import boto3  # type: ignore
    except ImportError:
        return None
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def download_prefix(bucket: str, prefix: str, dest: Path) -> None:
    client = _client()
    dest.mkdir(parents=True, exist_ok=True)
    if client is None:
        print(f"[local] skip download; using {dest} as s3://{bucket}/{prefix}")
        return
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            if key.endswith("/"):
                continue
            target = dest / Path(key).name
            client.download_file(bucket, key, str(target))
            print(f"downloaded s3://{bucket}/{key} -> {target}")


def upload_outputs(bucket: str, prefix: str, files: list[Path]) -> None:
    client = _client()
    if client is None:
        print(f"[local] processed files stay on disk (would upload to s3://{bucket}/{prefix})")
        for path in files:
            print(f"  {path}")
        return
    for path in files:
        key = f"{prefix.rstrip('/')}/{path.name}"
        extra = {"ContentType": "application/json"} if path.suffix == ".json" else {}
        client.upload_file(str(path), bucket, key, ExtraArgs=extra or None)
        print(f"uploaded {path} -> s3://{bucket}/{key}")


def lambda_handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """AWS Lambda entry: S3 ObjectCreated on the raw bucket."""
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]
    print(f"ingest trigger s3://{bucket}/{key}")

    raw_dir = Path(os.environ.get("PGR_RAW_DIR", ROOT / "data" / "raw"))
    output_dir = Path(os.environ.get("PGR_OUTPUT_DIR", ROOT / "output"))
    processed_bucket = os.environ.get("PGR_PROCESSED_BUCKET", DEFAULT_PROCESSED_BUCKET)

    download_prefix(bucket, os.path.dirname(key), raw_dir)
    paths = run(
        raw_dir=raw_dir,
        ref=ROOT / "data" / "ref" / "teams_2021.json",
        output_dir=output_dir,
        web_dir=ROOT / "web",
    )
    upload_outputs(processed_bucket, "processed", [paths["json"], paths["sqlite"]])
    return {"ok": True, "json": str(paths["json"]), "sqlite": str(paths["sqlite"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate S3 ingest + PGRScore process")
    parser.add_argument("--raw-bucket", default=os.environ.get("PGR_RAW_BUCKET", DEFAULT_RAW_BUCKET))
    parser.add_argument("--processed-bucket", default=os.environ.get("PGR_PROCESSED_BUCKET", DEFAULT_PROCESSED_BUCKET))
    parser.add_argument("--prefix", default="")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()

    download_prefix(args.raw_bucket, args.prefix, args.raw_dir)
    fake_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": args.raw_bucket},
                    "object": {"key": f"{args.prefix}games.csv".lstrip("/")},
                }
            }
        ]
    }
    os.environ["PGR_PROCESSED_BUCKET"] = args.processed_bucket
    os.environ["PGR_RAW_DIR"] = str(args.raw_dir)
    os.environ["PGR_OUTPUT_DIR"] = str(args.output_dir)
    result = lambda_handler(fake_event)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
