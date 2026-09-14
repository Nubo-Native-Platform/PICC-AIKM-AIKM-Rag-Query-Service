"""MinIO helpers for RAG image metadata."""

from typing import Any

from src.core.config import settings


def enrich_image_asset(image: dict[str, Any]) -> dict[str, Any] | None:
    object_key = image.get("object_key")
    bucket = image.get("bucket") or settings.MINIO_BUCKET
    if not object_key:
        print("[Warning] image asset missing object_key")
        return None
    if not bucket:
        print("[Warning] image asset missing bucket")
        return None
    return {
        **image,
        "bucket": bucket,
        "url": image.get("url") or "",
    }
