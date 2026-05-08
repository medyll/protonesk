#!/usr/bin/env python3
"""
Proton Mail Bridge — Cross-Platform Installer

Detects OS, installs dependencies, generates config, and sets up the service.

Usage:
    python scripts/install.py
    python scripts/install.py --uninstall
"""

import os
import sys
import platform
import subprocess
import importlib
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

MIN_PYTHON = (3, 11)
REQUIRED_PACKAGES = [
    "proton-python-client",
    "httpx",
    "requests",
    "python-gnupg",
    "pyyaml",
    "aiosmtpd",
    "keyring",
    "cryptography",
    "beautifulsoup4",
    "pyopenssl",
    "pyotp",
    "python-dotenv",
]

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"


# ── Helpers ───────────────────────────────────────────────────────────────────

def print_info(msg):
    print(f"\033[36m[INFO]\033[0m {msg}")


def print_ok(msg):
    print(f"\033[32m[OK]\033[0m   {msg}")


def print_warn(msg):
    print(f"\033[33m[WARN]\033[0m {msg}")


def print_err(msg):
    print(f"\033[31m[ERR]\033[0m  {msg}", file=sys.stderr)


def check_python_version():
    current = sys.version_info[:2]
    if current < MIN_PYTHON:
        print_err(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {current[0]}.{current[1]}")
        sys.exit(1)
    print_ok(f"Python {current[0]}.{current[1]} OK")


def install_deps():
    missing = []
    for pkg in REQUIRED_PACKAGES:
        pkg_name = pkg.replace("-", "_")
        try:
            importlib.import_module(pkg_name.split("[")[0])
        except ImportError:
            missing.append(pkg)

    if not missing:
        print_ok("All dependencies installed")
        return

    print_info(f"Installing {len(missing)} missing package(s): {', '.join(missing)}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")],
        cwd=PROJECT_ROOT
    )
    print_ok("Dependencies installed")


def generate_config():
    if CONFIG_FILE.exists():
        print_info(f"Config already exists at {CONFIG_FILE}")
        return

    print_info("Generating config.yaml...")

    import yaml

    config = {
        "imap_port": 1143,
        "smtp_port": 1025,
        "imap_host": "127.0.0.1",
        "smtp_host": "127.0.0.1",
        "local_password": "bridge",
        "tls": False,
        "log_level": "INFO",
    }

    # Interactive prompts
    try:
        imap_port = input(f"IMAP port [{config['imap_port']}]: ").strip()
        if imap_port:
            config["imap_port"] = int(imap_port)

        smtp_port = input(f"SMTP port [{config['smtp_port']}]: ").strip()
        if smtp_port:
            config["smtp_port"] = int(smtp_port)

        password = input(f"Local password [{config['local_password']}]: ").strip()
        if password:
            config["local_password"] = password

        tls = input("Enable TLS? (y/N): ").strip().lower()
        config["tls"] = tls == "y"
    except (EOFError, KeyboardInterrupt):
        print()
        print_warn("Using defaults")

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print_ok(f"Config written to {CONFIG_FILE}")


def setup_credentials():
    print_info("Setting up credentials...")
    try:
        subprocess.check_call(
            [sys.executable, str(PROJECT_ROOT / "src" / "secrets.py"), "setup"],
            cwd=PROJECT_ROOT
        )
    except subprocess.CalledProcessError:
        print_warn("Credential setup failed — run 'python src/secrets.py setup' manually")


def install_service():
    os_name = platform.system()

    if os_name == "Windows":
        script = SCRIPT_DIR / "install-service-windows.ps1"
        if not script.exists():
            print_warn("Windows service script not found")
            return
        print_info("Installing Windows service...")
        subprocess.check_call(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "install"],
            cwd=PROJECT_ROOT
        )
    elif os_name == "Linux":
        script = SCRIPT_DIR / "install-service-linux.sh"
        if not script.exists():
            print_warn("Linux service script not found")
            return
        os.chmod(script, 0o755)
        print_info("Installing systemd service...")
        subprocess.check_call([str(script), "install"], cwd=PROJECT_ROOT)
    else:
        print_warn(f"Auto-service install not supported on {os_name}")
        return

    print_ok("Service installed")


def print_summary(config=None):
    import yaml

    if config is None and CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f) or {}

    imap_port = config.get("imap_port", 1143) if config else 1143
    smtp_port = config.get("smtp_port", 1025) if config else 1025
    password = config.get("local_password", "bridge") if config else "bridge"

    print()
    print("=" * 50)
    print("  Proton Mail Bridge installed and ready")
    print("=" * 50)
    print()
    print(f"  IMAP:   127.0.0.1:{imap_port}  (password: {password})")
    print(f"  SMTP:   127.0.0.1:{smtp_port}")
    print()
    print("  Thunderbird: Add account → IMAP manual → 127.0.0.1:" + str(imap_port))
    print()
    print("  Start service:")
    if platform.system() == "Windows":
        print(f"    powershell .\\scripts\\install-service-windows.ps1 start")
    else:
        print(f"    systemctl --user start proton-bridge")
    print()


def do_uninstall():
    os_name = platform.system()

    if os_name == "Windows":
        script = SCRIPT_DIR / "install-service-windows.ps1"
        if script.exists():
            subprocess.check_call(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "uninstall"],
                cwd=PROJECT_ROOT
            )
    elif os_name == "Linux":
        script = SCRIPT_DIR / "install-service-linux.sh"
        if script.exists():
            subprocess.check_call([str(script), "uninstall"], cwd=PROJECT_ROOT)

    print_ok("Service uninstalled")

    # Ask about config/credentials
    try:
        cleanup = input("Remove config and credentials? (y/N): ").strip().lower()
        if cleanup == "y":
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
                print_info("Config removed")
            print_info("Credentials remain in OS keyring — remove manually if needed")
    except (EOFError, KeyboardInterrupt):
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if "--uninstall" in sys.argv:
        do_uninstall()
        return

    print("Proton Mail Bridge — Installer")
    print(f"OS: {platform.system()} {platform.release()}")

    check_python_version()
    install_deps()
    generate_config()
    setup_credentials()
    install_service()
    print_summary()


if __name__ == "__main__":
    main()
