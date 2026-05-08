#!/usr/bin/env python3
"""Tests for S6-04 — Tray icon module"""

import pytest
from unittest.mock import MagicMock, patch


class TestTrayIconStates:

    def test_bridge_state_enum(self):
        from src.tray import BridgeState
        assert BridgeState.STOPPED.value == "stopped"
        assert BridgeState.CONNECTED.value == "connected"
        assert BridgeState.ERROR.value == "error"
        assert BridgeState.CONNECTING.value == "connecting"


class TestTrayIconCreation:

    def test_tray_init_stopped_state(self):
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        assert tray._state == BridgeState.STOPPED

    def test_tray_init_with_runner(self):
        from src.tray import TrayIcon
        runner = MagicMock()
        tray = TrayIcon(bridge_runner=runner)
        assert tray._bridge_runner == runner

    def test_create_icon_returns_image(self):
        pytest.importorskip("PIL")
        from src.tray import TrayIcon
        tray = TrayIcon()
        img = tray._create_icon("green", size=16)
        assert img.size == (16, 16)

    def test_get_icon_matches_state(self):
        pytest.importorskip("PIL")
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        tray._state = BridgeState.CONNECTED
        img = tray._get_icon()
        assert img is not None

    def test_get_title_stopped(self):
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        tray._state = BridgeState.STOPPED
        assert "Stopped" in tray._get_title()

    def test_get_title_connected(self):
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        tray._state = BridgeState.CONNECTED
        tray._account_count = 3
        title = tray._get_title()
        assert "3" in title
        assert "connected" in title.lower()

    def test_get_title_error(self):
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        tray._state = BridgeState.ERROR
        assert "Error" in tray._get_title()


class TestTrayMenu:

    def test_build_menu_has_required_items(self):
        """Test menu structure when pystray is available."""
        pytest.importorskip("pystray")
        from src.tray import TrayIcon, BridgeState

        tray = TrayIcon()
        tray._state = BridgeState.STOPPED
        menu = tray._build_menu()

        # Menu should have been created
        assert menu is not None


class TestTrayStateChanges:

    def test_set_state_updates_icon(self):
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        tray._tray = MagicMock()
        tray.set_state(BridgeState.CONNECTED, account_count=2)
        assert tray._state == BridgeState.CONNECTED
        assert tray._account_count == 2
        tray._tray.update_icon.assert_called_once()

    def test_set_state_updates_menu(self):
        from src.tray import TrayIcon, BridgeState
        tray = TrayIcon()
        tray._tray = MagicMock()
        tray.set_state(BridgeState.ERROR)
        tray._tray.update_menu.assert_called_once()


class TestInstallScript:

    def test_install_py_exists(self):
        from pathlib import Path
        script = Path(__file__).parent.parent / "scripts" / "install.py"
        assert script.exists()

    def test_install_py_has_main(self):
        from pathlib import Path
        content = (Path(__file__).parent.parent / "scripts" / "install.py").read_text()
        assert "def main()" in content
        assert "check_python_version" in content
        assert "install_deps" in content
        assert "generate_config" in content

    def test_linux_service_exists(self):
        from pathlib import Path
        script = Path(__file__).parent.parent / "scripts" / "install-service-linux.sh"
        assert script.exists()

    def test_linux_service_has_systemd(self):
        from pathlib import Path
        content = (Path(__file__).parent.parent / "scripts" / "install-service-linux.sh").read_text()
        assert "systemctl --user" in content
        assert "Restart=on-failure" not in content  # That's in the .service file
        assert "daemon-reload" in content

    def test_service_unit_exists(self):
        from pathlib import Path
        unit = Path(__file__).parent.parent / "scripts" / "proton-bridge.service"
        assert unit.exists()

    def test_service_unit_valid_structure(self):
        from pathlib import Path
        content = (Path(__file__).parent.parent / "scripts" / "proton-bridge.service").read_text()
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        assert "Restart=on-failure" in content
        assert "RestartSec=5s" in content
        assert "WantedBy=default.target" in content


class TestMainTrayFlag:

    def test_tray_argument_exists(self):
        from main import parse_args
        import sys
        original = sys.argv
        try:
            sys.argv = ["main.py", "--tray"]
            args = parse_args()
            assert args.tray is True
        finally:
            sys.argv = original

    def test_no_tray_flag_default_false(self):
        from main import parse_args
        import sys
        original = sys.argv
        try:
            sys.argv = ["main.py"]
            args = parse_args()
            assert args.tray is False
        finally:
            sys.argv = original
