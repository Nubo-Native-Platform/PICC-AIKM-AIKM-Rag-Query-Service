"""Spring Cloud Config Server bootstrap and local override loading."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

logger = logging.getLogger(__name__)


def _ensure_bootstrap_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@dataclass(frozen=True)
class ConfigServerBootstrap:
    url: str
    app_name: str
    profile: str = "main"
    tag: str = "v1"
    timeout_seconds: float = 5.0
    required: bool = True
    allow_local_config_overrides: bool = False

    @property
    def endpoint(self) -> str:
        return f"{self.url.rstrip('/')}/{self.app_name}/{self.profile}/{self.tag}"


def normalize_key(key: str) -> str:
    return key.replace(".", "_").replace("-", "_").upper()


def _env_or_dotenv(key: str, default: str = "") -> str:
    dotenv_data = dotenv_values(Path.cwd() / ".env")
    value = os.getenv(key)
    if value is None:
        value = dotenv_data.get(key)
    return str(value or default).strip()


def _load_dotenv() -> dict[str, str]:
    return {
        normalize_key(str(key)): str(value).strip()
        for key, value in dotenv_values(Path.cwd() / ".env").items()
        if value is not None and str(value).strip()
    }


def load_bootstrap() -> ConfigServerBootstrap:
    return ConfigServerBootstrap(
        url=_env_or_dotenv("CONFIG_SERVER_URL"),
        app_name=_env_or_dotenv("CONFIG_APP_NAME"),
        profile=_env_or_dotenv("CONFIG_PROFILE", "main"),
        tag=_env_or_dotenv("CONFIG_TAG", "v1"),
        timeout_seconds=float(_env_or_dotenv("CONFIG_SERVER_TIMEOUT", "5")),
        required=_env_or_dotenv("CONFIG_SERVER_REQUIRED", "true").lower()
        in {"true", "1", "yes", "y", "on"},
        allow_local_config_overrides=_env_or_dotenv(
            "ALLOW_LOCAL_CONFIG_OVERRIDES", "false"
        ).lower()
        in {"true", "1", "yes", "y", "on"},
    )


def load_app_env(default: str = "") -> str:
    return _env_or_dotenv("APP_ENV", default)


def load_local_overrides(
    excluded_keys: set[str] | None = None,
    allowed_keys: set[str] | None = None,
) -> dict[str, str]:
    excluded = {normalize_key(key) for key in (excluded_keys or set())}
    allowed = {normalize_key(key) for key in allowed_keys} if allowed_keys else None
    overrides = _load_dotenv()
    for key, value in os.environ.items():
        normalized_key = normalize_key(key)
        if str(value).strip():
            overrides[normalized_key] = str(value).strip()
    return {
        key: value
        for key, value in overrides.items()
        if key not in excluded and value and (allowed is None or key in allowed)
    }


def fetch_config() -> tuple[dict[str, Any], ConfigServerBootstrap]:
    _ensure_bootstrap_logging()
    bootstrap = load_bootstrap()
    if not bootstrap.url or not bootstrap.app_name:
        missing = [
            key
            for key, value in {
                "CONFIG_SERVER_URL": bootstrap.url,
                "CONFIG_APP_NAME": bootstrap.app_name,
            }.items()
            if not value
        ]
        raise RuntimeError(
            "Config server bootstrap is incomplete. Missing: " + ", ".join(missing)
        )

    logger.info(
        "Fetching application config from config server app=%s profile=%s tag=%s url=%s",
        bootstrap.app_name,
        bootstrap.profile,
        bootstrap.tag,
        bootstrap.url,
    )

    try:
        response = requests.get(
            bootstrap.endpoint,
            timeout=bootstrap.timeout_seconds,
        )
        if response.status_code != 200:
            body = response.text[:500].replace("\n", " ").strip()
            raise RuntimeError(
                "Config server returned "
                f"status={response.status_code} endpoint={bootstrap.endpoint!r} body={body}"
            )
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Unable to fetch application config from config server "
            f"endpoint={bootstrap.endpoint!r}: {exc}"
        ) from exc

    config: dict[str, Any] = {}
    for property_source in payload.get("propertySources", []):
        source = property_source.get("source") or {}
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            config[normalize_key(str(key))] = value

    if not config:
        raise RuntimeError(
            "Config server response did not contain any propertySources values "
            f"endpoint={bootstrap.endpoint!r}"
        )

    return config, bootstrap
