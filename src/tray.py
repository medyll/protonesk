#!/usr/bin/env python3
"""
Protonesk — System Tray Icon

Provides a system tray icon with status display and bridge control.
Requires: pip install pystray pillow

States:
    Green  = Connected (all accounts active)
    Red    = Error (auth failure, service down)
    Grey   = Stopped

Usage:
    python main.py --tray
"""

import logging
import threading
import asyncio
import os
from pathlib import Path
from enum import Enum

try:
    from PIL import Image, ImageDraw

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None
    ImageDraw = None

try:
    import pystray

    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    pystray = None

logger = logging.getLogger(__name__)


class BridgeState(Enum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class TrayIcon:
    """System tray icon for Protonesk."""

    def __init__(self, bridge_runner=None):
        """
        Args:
            bridge_runner: Callable that starts the bridge (asyncio.run in thread)
        """
        self._state = BridgeState.STOPPED
        self._tray = None
        self._bridge_thread = None
        self._stop_event = threading.Event()
        self._bridge_runner = bridge_runner
        self._account_count = 0
        self._status_text = "Stopped"

    def _create_icon(self, color: str, size: int = 32):
        """Create a colored circle icon."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        colors = {
            "green": (34, 197, 94, 255),
            "red": (239, 68, 68, 255),
            "grey": (156, 163, 175, 255),
            "yellow": (234, 179, 8, 255),
        }
        fill = colors.get(color, colors["grey"])
        margin = 2
        draw.ellipse([margin, margin, size - margin, size - margin], fill=fill)
        return img

    def _get_icon(self):
        """Return icon matching current state."""
        color_map = {
            BridgeState.STOPPED: "grey",
            BridgeState.CONNECTING: "yellow",
            BridgeState.CONNECTED: "green",
            BridgeState.ERROR: "red",
        }
        return self._create_icon(color_map.get(self._state, "grey"))

    def _get_title(self) -> str:
        """Return tray tooltip title."""
        state_labels = {
            BridgeState.STOPPED: "Proton Bridge — Stopped",
            BridgeState.CONNECTING: "Proton Bridge — Connecting...",
            BridgeState.CONNECTED: f"Proton Bridge — {self._account_count} account(s) connected",
            BridgeState.ERROR: "Proton Bridge — Error",
        }
        return state_labels.get(self._state, "Proton Bridge")

    def _start_bridge(self):
        """Start bridge in background thread."""
        if self._bridge_thread and self._bridge_thread.is_alive():
            return

        if not self._bridge_runner:
            logger.warning("No bridge runner configured")
            return

        self._state = BridgeState.CONNECTING
        self._stop_event.clear()

        def _run():
            try:
                self._bridge_runner()
            except Exception as e:
                logger.error(f"Bridge crashed: {e}")
                self._state = BridgeState.ERROR
                if self._tray:
                    self._tray.update_icon()

        self._bridge_thread = threading.Thread(target=_run, daemon=True)
        self._bridge_thread.start()
        logger.info("Bridge starting in background thread")

    def _stop_bridge(self):
        """Signal bridge to stop."""
        self._stop_event.set()
        self._state = BridgeState.STOPPED
        if self._tray:
            self._tray.update_icon()
        logger.info("Bridge stop requested")

    def _open_config(self):
        """Open config.yaml in default editor."""
        config_path = Path("config.yaml")
        if config_path.exists():
            if os.name == "nt":
                os.startfile(str(config_path))
            elif os.name == "posix":
                os.system(f"xdg-open {config_path}")

    def _build_menu(self) -> tuple:
        """Build tray menu items."""
        from pystray import MenuItem, Menu

        status_item = MenuItem(self._get_title, enabled=False)

        if self._state == BridgeState.STOPPED:
            action_item = MenuItem("Start", lambda: self._start_bridge())
        else:
            action_item = MenuItem("Stop", lambda: self._stop_bridge())

        restart_item = MenuItem("Restart", lambda: (self._stop_bridge(), self._start_bridge()))

        return Menu(
            [
                status_item,
                MenuItem.separator(),
                MenuItem("Open config.yaml", lambda: self._open_config()),
                MenuItem.separator(),
                action_item,
                restart_item,
                MenuItem.separator(),
                MenuItem("Quit", lambda: (self._stop_bridge(), self._tray.stop())),
            ]
        )

    def set_state(self, state: BridgeState, account_count: int = 0):
        """Update tray state from bridge thread."""
        self._state = state
        self._account_count = account_count
        if self._tray:
            self._tray.update_icon()
            self._tray.update_menu()

    def run(self):
        """Start the tray icon (blocks until quit)."""
        if not HAS_PYSTRAY:
            logger.warning("pystray not installed — run: pip install pystray pillow")
            return

        self._tray = pystray.Icon(
            "proton_bridge",
            self._get_icon(),
            self._get_title(),
            self._build_menu(),
        )

        logger.info("Tray icon starting")
        self._tray.run()
        logger.info("Tray icon stopped")


def create_tray_runner(args, cfg):
    """Create a callable that runs the bridge for tray mode."""

    def _run():
        from main import run

        asyncio.run(run(args))

    return _run
