"""Application settings loaded from the config server."""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.core.config_server import (
    fetch_config,
    load_app_env,
    load_bootstrap,
    load_local_overrides,
)

logger = logging.getLogger(__name__)


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


class Settings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    RAG_SERVICE_APP_NAME: str = Field(default="", alias="RAG_SERVICE_APP_NAME")
    APP_ENV: str = Field(default_factory=load_app_env)

    OPENAI_API_KEY: str = Field(default="", alias="OPENAI_API_KEY")
    EMBEDDING_MODEL: str = Field(default="", alias="EMBEDDING_MODEL")
    EMBEDDING_DIMENSION: int = Field(default=3072, alias="EMBEDDING_DIMENSION")
    LOCAL_EMBEDDING_MODEL: str = Field(default="", alias="LOCAL_EMBEDDING_MODEL")

    MILVUS_HOST: str = Field(default="", alias="MILVUS_HOST")
    MILVUS_PORT: int = Field(default=19530, alias="MILVUS_PORT")
    MILVUS_DB_NAME: str = Field(default="", alias="MILVUS_DB_NAME")
    MILVUS_COLLECTION_NAME: str = Field(default="", alias="MILVUS_COLLECTION_NAME")
    MILVUS_COLLECTION_NAME_LOCAL: str = Field(
        default="", alias="MILVUS_COLLECTION_NAME_LOCAL"
    )

    OLLAMA_BASE_URL: str = Field(default="", alias="OLLAMA_BASE_URL")
    RAG_SUMMARIZER_PUBLIC_LLM: str = Field(
        default="", alias="RAG_SUMMARIZER_PUBLIC_LLM"
    )
    RAG_SUMMARIZER_LOCAL_LLM: str = Field(default="", alias="RAG_SUMMARIZER_LOCAL_LLM")
    GET_SUMMARY_TIMEOUT_LOCAL: int = Field(default=120, alias="GET_SUMMARY_TIMEOUT_LOCAL")
    RAG_SUMMARY_MAX_WORDS: int = Field(default=1000, alias="RAG_SUMMARY_MAX_WORDS")
    RAG_ONLY_SYSTEM_PROMPT: Optional[str] = Field(
        default=None, alias="RAG_ONLY_SYSTEM_PROMPT"
    )
    RAG_WITH_PUBLIC_INFO_SYSTEM_PROMPT: Optional[str] = Field(
        default=None, alias="RAG_WITH_PUBLIC_INFO_SYSTEM_PROMPT"
    )
    PUBLIC_INFO_ONLY_SYSTEM_PROMPT: Optional[str] = Field(
        default=None, alias="PUBLIC_INFO_ONLY_SYSTEM_PROMPT"
    )

    MINIO_HOST: str = Field(default="", alias="MINIO_HOST")
    MINIO_ROOT_USER: str = Field(default="", alias="MINIO_ROOT_USER")
    MINIO_ROOT_PASSWORD: str = Field(default="", alias="MINIO_ROOT_PASSWORD")
    MINIO_SECURE: bool = Field(default=False, alias="MINIO_SECURE")
    MINIO_BUCKET: str = Field(default="", alias="MINIO_BUCKET")
    MINIO_PRESIGNED_URL_EXPIRY_SECONDS: int = Field(
        default=3600, alias="MINIO_PRESIGNED_URL_EXPIRY_SECONDS"
    )


REQUIRED_CONFIG_KEYS = {
    "RAG_SERVICE_APP_NAME",
    "OPENAI_API_KEY",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSION",
    "LOCAL_EMBEDDING_MODEL",
    "MILVUS_HOST",
    "MILVUS_PORT",
    "MILVUS_DB_NAME",
    "MILVUS_COLLECTION_NAME",
    "MILVUS_COLLECTION_NAME_LOCAL",
    "OLLAMA_BASE_URL",
    "RAG_SUMMARIZER_PUBLIC_LLM",
    "RAG_SUMMARIZER_LOCAL_LLM",
    "GET_SUMMARY_TIMEOUT_LOCAL",
    "RAG_SUMMARY_MAX_WORDS",
    "RAG_ONLY_SYSTEM_PROMPT",
    "RAG_WITH_PUBLIC_INFO_SYSTEM_PROMPT",
    "PUBLIC_INFO_ONLY_SYSTEM_PROMPT",
    "MINIO_HOST",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "MINIO_BUCKET",
    "MINIO_PRESIGNED_URL_EXPIRY_SECONDS",
}

SECRET_CONFIG_KEYS = {
    "MINIO_ROOT_PASSWORD",
    "OPENAI_API_KEY",
}

BOOTSTRAP_CONFIG_KEYS = {
    "CONFIG_SERVER_URL",
    "CONFIG_APP_NAME",
    "CONFIG_PROFILE",
    "CONFIG_TAG",
    "CONFIG_SERVER_TIMEOUT",
    "CONFIG_SERVER_REQUIRED",
    "ALLOW_LOCAL_CONFIG_OVERRIDES",
    "APP_ENV",
}


def _settings_aliases() -> set[str]:
    aliases: set[str] = set()
    for field_name, field_info in Settings.model_fields.items():
        aliases.add(str(field_info.alias or field_name))
        validation_alias = field_info.validation_alias
        if validation_alias:
            aliases.add(str(validation_alias))
    return aliases


def _validate_required_config(config: dict[str, object]) -> None:
    missing = sorted(key for key in REQUIRED_CONFIG_KEYS if _is_missing(config.get(key)))
    fetched = len(REQUIRED_CONFIG_KEYS) - len(missing)

    if missing:
        logger.error(
            "Effective config validation failed: resolved %s/%s required keys; missing=%s",
            fetched,
            len(REQUIRED_CONFIG_KEYS),
            ", ".join(missing),
        )
        raise RuntimeError("Missing required config values: " + ", ".join(missing))

    logger.info(
        "Effective config validation succeeded: resolved all %s required keys",
        len(REQUIRED_CONFIG_KEYS),
    )


def _load_config_server_values() -> tuple[dict[str, object], bool]:
    bootstrap = load_bootstrap()
    try:
        values, _ = fetch_config()
        return values, True
    except Exception:
        if bootstrap.required:
            raise
        logger.exception(
            "Config server fetch failed, continuing with local env overrides "
            "because CONFIG_SERVER_REQUIRED=false"
        )
        return {}, False


_bootstrap = load_bootstrap()
_config_server_values, _config_server_loaded = _load_config_server_values()
_allowed_override_keys = _settings_aliases() | REQUIRED_CONFIG_KEYS | SECRET_CONFIG_KEYS
_local_overrides = (
    load_local_overrides(
        excluded_keys=BOOTSTRAP_CONFIG_KEYS,
        allowed_keys=_allowed_override_keys,
    )
    if _bootstrap.allow_local_config_overrides or not _config_server_loaded
    else {}
)
if not _bootstrap.allow_local_config_overrides and _config_server_loaded:
    logger.info(
        "Local runtime config overrides disabled; using config-server values only"
    )
_effective_config = {**_config_server_values, **_local_overrides}
if _local_overrides:
    logger.info(
        "Applied %s non-empty local config override(s): %s",
        len(_local_overrides),
        ", ".join(sorted(_local_overrides)),
    )
_validate_required_config(_effective_config)
settings = Settings(**_effective_config)
