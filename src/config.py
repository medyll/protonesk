#!/usr/bin/env python3
"""
Protonesk — Config loader

Merges config.yaml defaults with CLI argparse Namespace.
CLI args always win over config file.

Supports multi-account via `accounts` key in config.yaml.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

CONFIG_FILE = Path("config.yaml")

DEFAULTS = {
    "imap_port": 1143,
    "smtp_port": 1025,
    "imap_host": "127.0.0.1",
    "smtp_host": "127.0.0.1",
    "local_password": "bridge",
    "tls": False,
    "log_level": "INFO",
}


class ConfigError(Exception):
    """Raised when config.yaml has invalid structure."""

    pass


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML file, return empty dict if missing or invalid."""
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return {k: v for k, v in data.items() if v is not None}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return {}


def _validate_accounts(accounts: Any) -> List[Dict[str, str]]:
    """Validate and normalize the accounts list.

    Returns normalized list of account dicts with 'username' and 'label' keys.
    Raises ConfigError on invalid structure.
    """
    if accounts is None:
        return []

    if not isinstance(accounts, list):
        raise ConfigError(f"'accounts' must be a list, got {type(accounts).__name__}")

    if len(accounts) == 0:
        raise ConfigError("'accounts' is present but empty — at least one account is required")

    normalized = []
    for i, account in enumerate(accounts):
        if not isinstance(account, dict):
            raise ConfigError(f"Account at index {i} must be a dict, got {type(account).__name__}")

        username = account.get("username")
        if not username or not isinstance(username, str):
            raise ConfigError(f"Account at index {i} is missing required 'username' field")

        label = account.get("label", username)
        if not isinstance(label, str):
            raise ConfigError(f"Account at index {i} has invalid 'label' (must be string)")

        normalized.append(
            {
                "username": username,
                "label": label,
            }
        )

    return normalized


def load_config(args=None) -> Dict[str, Any]:
    """
    Merge config sources in priority order (lowest → highest):
      1. DEFAULTS
      2. config.yaml
      3. CLI args (argparse Namespace)

    Returns merged dict with all bridge settings.
    If 'accounts' key is present in config.yaml, it is validated and normalized.
    Backward compatible: if 'accounts' is absent, single-account mode via keyring.
    """
    config = dict(DEFAULTS)

    file_config = _load_yaml(CONFIG_FILE)

    # Validate and normalize accounts if present
    if "accounts" in file_config:
        file_config["accounts"] = _validate_accounts(file_config["accounts"])

    config.update(file_config)

    if args is not None:
        for key, value in vars(args).items():
            # CLI arg wins only if it differs from argparse default
            # (non-None and not the same as our DEFAULTS where applicable)
            if value is not None:
                config[key] = value

    return config
