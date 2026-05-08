#!/usr/bin/env python3
"""Tests for TLS module — S3-01 + S3-02"""

import ssl
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestCertGeneration:

    def test_is_cert_expired_no_file(self, tmp_path):
        from src import tls as tls_mod
        with patch.object(tls_mod, "CERT_FILE", tmp_path / "missing.crt"):
            assert tls_mod._is_cert_expired() is True

    def test_generate_cert_creates_files(self, tmp_path):
        from src import tls as tls_mod
        with patch.object(tls_mod, "CERT_DIR", tmp_path), \
             patch.object(tls_mod, "CERT_FILE", tmp_path / "server.crt"), \
             patch.object(tls_mod, "KEY_FILE", tmp_path / "server.key"):
            tls_mod._generate_cert()
            assert (tmp_path / "server.crt").exists()
            assert (tmp_path / "server.key").exists()

    def test_generated_cert_not_expired(self, tmp_path):
        from src import tls as tls_mod
        with patch.object(tls_mod, "CERT_DIR", tmp_path), \
             patch.object(tls_mod, "CERT_FILE", tmp_path / "server.crt"), \
             patch.object(tls_mod, "KEY_FILE", tmp_path / "server.key"):
            tls_mod._generate_cert()
            assert tls_mod._is_cert_expired() is False

    def test_get_ssl_context_returns_ssl_context(self, tmp_path):
        from src import tls as tls_mod
        with patch.object(tls_mod, "CERT_DIR", tmp_path), \
             patch.object(tls_mod, "CERT_FILE", tmp_path / "server.crt"), \
             patch.object(tls_mod, "KEY_FILE", tmp_path / "server.key"):
            ctx = tls_mod.get_ssl_context()
            assert isinstance(ctx, ssl.SSLContext)

    def test_cert_info_no_cert(self, tmp_path):
        from src import tls as tls_mod
        with patch.object(tls_mod, "CERT_FILE", tmp_path / "missing.crt"):
            info = tls_mod.cert_info()
            assert info["exists"] is False

    def test_cert_info_with_cert(self, tmp_path):
        from src import tls as tls_mod
        with patch.object(tls_mod, "CERT_DIR", tmp_path), \
             patch.object(tls_mod, "CERT_FILE", tmp_path / "server.crt"), \
             patch.object(tls_mod, "KEY_FILE", tmp_path / "server.key"):
            tls_mod._generate_cert()
            info = tls_mod.cert_info()
            assert info["exists"] is True
            assert "expires" in info
            assert info["expired"] is False


class TestIMAPServerTLS:
    @pytest.mark.asyncio
    async def test_imap_server_accepts_ssl_context(self):
        from src.imap_server import ProtonIMAPServer
        bridge = MagicMock()
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        server = ProtonIMAPServer(bridge, ssl_context=mock_ctx)
        assert server.ssl_context is mock_ctx

    @pytest.mark.asyncio
    async def test_imap_server_no_ssl_by_default(self):
        from src.imap_server import ProtonIMAPServer
        bridge = MagicMock()
        server = ProtonIMAPServer(bridge)
        assert server.ssl_context is None


class TestSMTPServerTLS:
    def test_smtp_server_accepts_ssl_context(self):
        from src.smtp_server import ProtonSMTPServer
        mock_send = MagicMock()
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        server = ProtonSMTPServer(mock_send, ssl_context=mock_ctx)
        assert server.ssl_context is mock_ctx

    def test_smtp_server_no_ssl_by_default(self):
        from src.smtp_server import ProtonSMTPServer
        mock_send = MagicMock()
        server = ProtonSMTPServer(mock_send)
        assert server.ssl_context is None

    def test_smtp_server_passes_ssl_to_controller(self):
        from src.smtp_server import ProtonSMTPServer
        mock_send = MagicMock()
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        server = ProtonSMTPServer(mock_send, ssl_context=mock_ctx)
        with patch("src.smtp_server.Controller") as MockCtrl:
            mock_instance = MagicMock()
            MockCtrl.return_value = mock_instance
            server.start()
            call_kwargs = MockCtrl.call_args[1]
            assert call_kwargs.get("ssl_context") is mock_ctx
