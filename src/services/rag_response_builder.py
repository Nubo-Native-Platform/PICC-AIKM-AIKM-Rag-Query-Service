"""Helpers for shaping RAG API response metadata."""

from typing import Any

from src.services.minio_storage import enrich_image_asset


def collect_rag_images(
    results: list[dict[str, Any]],
    max_images: int = 3,
) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in results:
        metadata = result.get("metadata") or {}
        candidate_images = [
            image
            for image in metadata.get("images") or []
            if isinstance(image, dict) and image.get("type") == "figure"
        ]

        for image in candidate_images:
            key = image.get("asset_id") or image.get("object_key")
            if not key or key in seen:
                continue
            seen.add(key)
            enriched = {
                **image,
                "doc_name": image.get("doc_name") or metadata.get("doc_name"),
                "page_number": image.get("page_number") or metadata.get("page_number"),
            }
            asset = enrich_image_asset(enriched)
            if asset:
                images.append(asset)
            if len(images) >= max_images:
                return images
    if not images and results:
        print("[Warning] no RAG images found in retrieved chunks")
    return images


def collect_rag_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for result in results:
        metadata = result.get("metadata") or {}
        key = (
            result.get("source"),
            metadata.get("doc_name"),
            metadata.get("page_number"),
        )
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "score": result.get("score", 0.0),
                "source": result.get("source"),
                "doc_type": result.get("doc_type"),
                "collection": result.get("collection"),
                "doc_name": metadata.get("doc_name"),
                "page_number": metadata.get("page_number"),
            }
        )
    return sources
