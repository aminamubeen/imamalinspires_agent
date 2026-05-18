"""
upload_to_r2.py
---------------
Uploads the generated quote images to a Cloudflare R2 bucket
using boto3 (S3-compatible API).

Required environment variables:
    R2_ACCOUNT_ID        - Cloudflare account ID
    R2_ACCESS_KEY_ID     - R2 access key
    R2_SECRET_ACCESS_KEY - R2 secret key
    R2_BUCKET_NAME       - Bucket name
    R2_PUBLIC_URL        - Public base URL for the bucket
                           e.g. "https://pub-xxxx.r2.dev"
"""

import os
import boto3
from pathlib import Path
from botocore.config import Config


# ── Client ───────────────────────────────────────────────────────────────────
def _get_r2_client():
    account_id = os.environ["R2_ACCOUNT_ID"]
    access_key = os.environ["R2_ACCESS_KEY_ID"]
    secret_key = os.environ["R2_SECRET_ACCESS_KEY"]
    endpoint   = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url          = endpoint,
        aws_access_key_id     = access_key,
        aws_secret_access_key = secret_key,
        config                = Config(signature_version="s3v4"),
        region_name           = "auto",
    )


# ── Upload ───────────────────────────────────────────────────────────────────
def upload_images(image_paths: dict) -> dict:
    """
    Uploads all images in image_paths to R2.

    image_paths keys expected:
        instagram_dark, instagram_light, pinterest_dark, pinterest_light

    Returns same keys mapped to their full public URLs, e.g.:
        {
            "instagram_dark":  "https://pub-xxxx.r2.dev/quotes/instagram_saying_21_20250520_dark.jpg",
            ...
        }
    """
    bucket     = os.environ["R2_BUCKET_NAME"]
    public_url = os.environ["R2_PUBLIC_URL"].rstrip("/")
    client     = _get_r2_client()
    urls       = {}

    for label, file_path in image_paths.items():
        path = Path(file_path)
        if not path.exists():
            print(f"  ⚠  Skipping {label}: file not found at {file_path}")
            continue

        object_key = f"quotes/{path.name}"

        print(f"  Uploading {label} → r2://{bucket}/{object_key} ...")
        client.upload_file(
            Filename    = str(path),
            Bucket      = bucket,
            Key         = object_key,
            ExtraArgs   = {"ContentType": "image/jpeg"},
        )

        urls[label] = f"{public_url}/{object_key}"
        print(f"  ✓ {label}: {urls[label]}")

    return urls


# ── Entry point (for testing standalone) ─────────────────────────────────────
if __name__ == "__main__":
    from generate_image import generate

    result = generate()
    image_paths = {
        "instagram_dark":  result["instagram_dark"],
        "instagram_light": result["instagram_light"],
        "pinterest_dark":  result["pinterest_dark"],
        "pinterest_light": result["pinterest_light"],
    }

    urls = upload_images(image_paths)
    print("\nUploaded URLs:")
    for k, v in urls.items():
        print(f"  {k}: {v}")
