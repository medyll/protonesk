#!/usr/bin/env bash
# Protonesk — MCP Server Linux systemd Service Installer
#
# Usage:
#   ./install-mcp-service-linux.sh install
#   ./install-mcp-service-linux.sh uninstall
#   ./install-mcp-service-linux.sh status
#
# Installs the MCP server (streamable-http) as a user service for keyring access.
# Override bind before install: PROTON_MCP_HOST / PROTON_MCP_PORT.

set -euo pipefail

SERVICE_NAME="proton-mcp"
SERVICE_FILE="proton-mcp.service"
UNIT_DIR="$HOME/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

MCP_HOST="${PROTON_MCP_HOST:-127.0.0.1}"
MCP_PORT="${PROTON_MCP_PORT:-8787}"

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

    mkdir -p "$UNIT_DIR"

    local target_unit="$UNIT_DIR/$SERVICE_FILE"
    sed \
        -e "s|/usr/bin/python3|$PYTHON_PATH|g" \
        -e "s|/opt/proton-bridge|$PROJECT_ROOT|g" \
        -e "s|PROTON_MCP_HOST=127.0.0.1|PROTON_MCP_HOST=$MCP_HOST|g" \
        -e "s|PROTON_MCP_PORT=8787|PROTON_MCP_PORT=$MCP_PORT|g" \
        "$SCRIPT_DIR/$SERVICE_FILE" > "$target_unit"

    info "Service unit written to $target_unit"

    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"

    ok "Service '$SERVICE_NAME' installed and enabled"
    info "Endpoint: http://$MCP_HOST:$MCP_PORT/mcp"
    info "Start with: systemctl --user start $SERVICE_NAME"
    info "Logs:     journalctl --user -u $SERVICE_NAME -f"
}

do_uninstall() {
    check_systemd

    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true

    local target_unit="$UNIT_DIR/$SERVICE_FILE"
    if [ -f "$target_unit" ]; then
        rm "$target_unit"
        info "Removed $target_unit"
    fi

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
        info "Endpoint: http://$MCP_HOST:$MCP_PORT/mcp"
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
