#!/usr/bin/env python3
"""Tests for config loader — S3-04 + S4-01 (multi-account)"""

import argparse
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path


def make_args(**kwargs):
    defaults = {
        "imap_port": None, "smtp_port": None,
        "imap_host": None, "smtp_host": None,
        "local_password": None, "tls": None,
        "log_level": None, "imap_only": False, "smtp_only": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestLoadConfig:

    def test_defaults_when_no_file_no_args(self, tmp_path):
        from src.config import load_config, DEFAULTS
        with patch("src.config.CONFIG_FILE", tmp_path / "missing.yaml"):
            cfg = load_config()
        for key, val in DEFAULTS.items():
            assert cfg[key] == val

    def test_yaml_overrides_defaults(self, tmp_path):
        yaml_content = "imap_port: 2143\nsmtp_port: 2025\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert cfg["imap_port"] == 2143
        assert cfg["smtp_port"] == 2025

    def test_cli_args_override_yaml(self, tmp_path):
        yaml_content = "imap_port: 2143\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        args = make_args(imap_port=3143)
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config(args)
        assert cfg["imap_port"] == 3143

    def test_missing_config_file_uses_defaults(self, tmp_path):
        from src.config import load_config, DEFAULTS
        with patch("src.config.CONFIG_FILE", tmp_path / "nonexistent.yaml"):
            cfg = load_config()
        assert cfg["imap_port"] == DEFAULTS["imap_port"]

    def test_tls_flag_from_args(self, tmp_path):
        args = make_args(tls=True)
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", tmp_path / "missing.yaml"):
            cfg = load_config(args)
        assert cfg["tls"] is True

    def test_tls_from_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("tls: true\n")
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert cfg["tls"] is True

    def test_invalid_yaml_falls_back_to_defaults(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("{invalid yaml: [")
        from src.config import load_config, DEFAULTS
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert cfg["imap_port"] == DEFAULTS["imap_port"]

    def test_log_level_from_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("log_level: DEBUG\n")
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert cfg["log_level"] == "DEBUG"

    def test_local_password_from_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("local_password: mysecret\n")
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert cfg["local_password"] == "mysecret"


class TestMultiAccountConfig:
    """S4-01 — Multi-account config.yaml support"""

    def test_accounts_loaded_from_yaml(self, tmp_path):
        yaml_content = """\
accounts:
  - username: perso@proton.me
    label: perso
  - username: pro@proton.me
    label: pro
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert "accounts" in cfg
        assert len(cfg["accounts"]) == 2
        assert cfg["accounts"][0]["username"] == "perso@proton.me"
        assert cfg["accounts"][0]["label"] == "perso"
        assert cfg["accounts"][1]["username"] == "pro@proton.me"
        assert cfg["accounts"][1]["label"] == "pro"

    def test_label_defaults_to_username(self, tmp_path):
        yaml_content = """\
accounts:
  - username: solo@proton.me
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert cfg["accounts"][0]["label"] == "solo@proton.me"

    def test_backward_compat_no_accounts_key(self, tmp_path):
        yaml_content = "imap_port: 2143\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config
        with patch("src.config.CONFIG_FILE", cfg_file):
            cfg = load_config()
        assert "accounts" not in cfg

    def test_empty_accounts_raises_error(self, tmp_path):
        yaml_content = "accounts: []\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config, ConfigError
        with patch("src.config.CONFIG_FILE", cfg_file):
            with pytest.raises(ConfigError, match="empty"):
                load_config()

    def test_accounts_not_list_raises_error(self, tmp_path):
        yaml_content = "accounts: not_a_list\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config, ConfigError
        with patch("src.config.CONFIG_FILE", cfg_file):
            with pytest.raises(ConfigError, match="must be a list"):
                load_config()

    def test_account_missing_username_raises_error(self, tmp_path):
        yaml_content = """\
accounts:
  - label: only_label
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config, ConfigError
        with patch("src.config.CONFIG_FILE", cfg_file):
            with pytest.raises(ConfigError, match="missing required 'username'"):
                load_config()

    def test_account_not_dict_raises_error(self, tmp_path):
        yaml_content = """\
accounts:
  - just_a_string
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        from src.config import load_config, ConfigError
        with patch("src.config.CONFIG_FILE", cfg_file):
            with pytest.raises(ConfigError, match="must be a dict"):
                load_config()
