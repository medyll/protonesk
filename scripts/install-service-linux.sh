#!/usr/bin/env bash
# Protonesk — Linux systemd Service Installer
#
# Usage:
#   ./install-service-linux.sh install
#   ./install-service-linux.sh uninstall
#   ./install-service-linux.sh status
#
# Installs as a user service (systemctl --user) for keyring access.

set -euo pipefail

SERVICE_NAME="proton-bridge"
SERVICE_FILE="proton-bridge.service"
UNIT_DIR="$HOME/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Helpers ───────────────────────────────────────────────────────────────────

info()  { echo "[INFO] $*"; }
ok()    { echo "[OK]   $*"; }
warn()  { echo "[WARN] $*"; }
err()   { echo "[ERR]  $*" >&2; }

check_systemd() {
    if ! command -v systemctl &>/dev/null; then
        err "systemctl not found. This script requires systemd."
        exit 1
    fi
}

check_python() {
    if ! command -v python3 &>/dev/null; then
        err "python3 not found in PATH."
        exit 1
    fi
    PYTHON_PATH="$(command -v python3)"
}

# ── Actions ───────────────────────────────────────────────────────────────────

do_install() {
    check_systemd
    check_python

    # Create user unit directory
    mkdir -p "$UNIT_DIR"

    # Generate service file with correct paths
    local target_unit="$UNIT_DIR/$SERVICE_FILE"
    sed \
        -e "s|/usr/bin/python3|$PYTHON_PATH|g" \
        -e "s|/opt/proton-bridge|$PROJECT_ROOT|g" \
        "$SCRIPT_DIR/$SERVICE_FILE" > "$target_unit"

    info "Service unit written to $target_unit"

    # Reload systemd user daemon
    systemctl --user daemon-reload

    # Enable service (start on login)
    systemctl --user enable "$SERVICE_NAME"

    ok "Service '$SERVICE_NAME' installed and enabled"
    info "Start with: systemctl --user start $SERVICE_NAME"
    info "Logs:     journalctl --user -u $SERVICE_NAME -f"
}

do_uninstall() {
    check_systemd

    # Stop and disable
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true

    # Remove unit file
    local target_unit="$UNIT_DIR/$SERVICE_FILE"
    if [ -f "$target_unit" ]; then
        rm "$target_unit"
        info "Removed $target_unit"
    fi

    # Reload
    systemctl --user daemon-reload

    ok "Service '$SERVICE_NAME' uninstalled"
}

do_status() {
    check_systemd

    if ! systemctl --user is-enabled "$SERVICE_NAME" &>/dev/null; then
        info "Service '$SERVICE_NAME' is not installed"
        info "Install with: $0 install"
        return
    fi

    local state
    state=$(systemctl --user is-active "$SERVICE_NAME" 2>/dev/null || echo "inactive")

    if [ "$state" = "active" ]; then
        ok "Service '$SERVICE_NAME' is running"
    else
        warn "Service '$SERVICE_NAME' is $state"
        info "Start with: systemctl --user start $SERVICE_NAME"
    fi

    info "Logs: journalctl --user -u $SERVICE_NAME -f"
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "${1:-}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    status)    do_status ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
