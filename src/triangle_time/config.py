"""
Configuration module for the triangle-time system.

Single source of truth for:
- Azure connection settings
- Default model hyperparameters

All values can be overridden via environment variables in Azure / local.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class Config:
    """
    Runtime configuration for the triangle-time system.

    All fields default from environment variables but can be overridden
    programmatically by constructing Config(...) manually if needed.
    """

    # Azure Blob Storage (for CSV-style "Excel but in the cloud" usage)
    azure_blob_connection_string: Optional[str] = None
    azure_blob_container_name: Optional[str] = None

    # (Optional) Azure SQL, if you later extend data_io to use SQL.
    azure_sql_connection_string: Optional[str] = None

    # Model hyperparameters
    use_entropy: bool = True
    default_eta: float = 0.0

    @classmethod
    def from_env(cls) -> "Config":
        """
        Construct a Config object by reading environment variables.

        Environment variables (all optional):
        - TT_AZURE_BLOB_CONNECTION_STRING
        - TT_AZURE_BLOB_CONTAINER_NAME
        - TT_AZURE_SQL_CONNECTION_STRING
        - TT_USE_ENTROPY  (true/false)
        - TT_DEFAULT_ETA  (float)
        """
        return cls(
            azure_blob_connection_string=os.getenv(
                "TT_AZURE_BLOB_CONNECTION_STRING"
            ),
            azure_blob_container_name=os.getenv(
                "TT_AZURE_BLOB_CONTAINER_NAME"
            ),
            azure_sql_connection_string=os.getenv(
                "TT_AZURE_SQL_CONNECTION_STRING"
            ),
            use_entropy=_get_env_bool("TT_USE_ENTROPY", default=True),
            default_eta=_get_env_float("TT_DEFAULT_ETA", default=0.0),
        )


# Convenience singleton-style accessor if you want a shared config
_DEFAULT_CONFIG: Optional[Config] = None


def get_config(force_reload: bool = False) -> Config:
    """
    Return a process-wide Config instance.

    Use `force_reload=True` if environment variables changed at runtime
    and you want to refresh.
    """
    global _DEFAULT_CONFIG
    if _DEFAULT_CONFIG is None or force_reload:
        _DEFAULT_CONFIG = Config.from_env()
    return _DEFAULT_CONFIG
