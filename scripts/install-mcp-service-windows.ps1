<#
.SYNOPSIS
    Protonesk — MCP Server Windows Service Manager (NSSM)

.DESCRIPTION
    Installs the Protonesk MCP server as an auto-start Windows service using NSSM,
    running over streamable-http so LLM agents can connect over the network at boot.
    Reuses the nssm.exe downloaded by install-service-windows.ps1; if absent, run the
    bridge installer first (it fetches NSSM).

    Service runs under the current user account to keep Windows Credential Manager
    (keyring) access.

.PARAMETER Action
    One of: install, uninstall, start, stop, status

.EXAMPLE
    .\install-mcp-service-windows.ps1 install
    .\install-mcp-service-windows.ps1 start
    .\install-mcp-service-windows.ps1 status
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("install", "uninstall", "start", "stop", "status")]
    [string]$Action
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Constants ─────────────────────────────────────────────────────────────────

$SERVICE_NAME = "ProtonMailMCP"
$DISPLAY_NAME = "Protonesk MCP"
$DESCRIPTION = "Protonesk — MCP server (streamable-http) for LLM agents"
$APPDATA_DIR = Join-Path $env:LOCALAPPDATA "ProtonBridge"
$NSSM_PATH = Join-Path $APPDATA_DIR "nssm.exe"
$LOG_DIR = Join-Path $APPDATA_DIR "logs"
$LOG_FILE = Join-Path $LOG_DIR "mcp.log"
$LOG_ROTATE_MB = 10

# HTTP bind (override before install if you want different host/port)
$MCP_HOST = if ($env:PROTON_MCP_HOST) { $env:PROTON_MCP_HOST } else { "127.0.0.1" }
$MCP_PORT = if ($env:PROTON_MCP_PORT) { $env:PROTON_MCP_PORT } else { "8787" }

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR
$MCP_PY = Join-Path $PROJECT_ROOT "src\mcp_server.py"

# ── Helpers ───────────────────────────────────────────────────────────────────

function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Message) Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err  { param([string]$Message) Write-Host "[ERR]  $Message" -ForegroundColor Red }

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Get-PythonPath {
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command "python3" -ErrorAction SilentlyContinue }
    if (-not $python) { throw "Python not found in PATH. Install Python 3.11+ and add to PATH." }
    return $python.Source
}

function Get-ServiceStatus {
    $service = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if (-not $service) { return "not_installed" }
    return $service.Status.ToString().ToLower()
}

# ── Actions ───────────────────────────────────────────────────────────────────

function Do-Install {
    $status = Get-ServiceStatus
    if ($status -ne "not_installed") {
        Write-Warn "Service '$SERVICE_NAME' already exists (status: $status)"
        return
    }

    if (-not (Test-Path $NSSM_PATH)) {
        throw "nssm.exe not found at $NSSM_PATH. Run install-service-windows.ps1 install first (it downloads NSSM)."
    }
    if (-not (Test-Path $MCP_PY)) { throw "mcp_server.py not found at $MCP_PY" }

    $PYTHON_EXE = Get-PythonPath
    Write-Info "Using Python: $PYTHON_EXE"
    Ensure-Directory $LOG_DIR

    Write-Info "Installing service '$SERVICE_NAME' (http://${MCP_HOST}:${MCP_PORT}/mcp)..."

    & $NSSM_PATH install $SERVICE_NAME $PYTHON_EXE $MCP_PY | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "NSSM install failed with exit code $LASTEXITCODE" }

    & $NSSM_PATH set $SERVICE_NAME DisplayName $DISPLAY_NAME | Out-Null
    & $NSSM_PATH set $SERVICE_NAME Description $DESCRIPTION | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppDirectory $PROJECT_ROOT | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppStdout $LOG_FILE | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppStderr $LOG_FILE | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppRotateFiles 1 | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppRotateBytes ($LOG_ROTATE_MB * 1024 * 1024) | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppRotateOnline 1 | Out-Null

    # HTTP transport via environment
    & $NSSM_PATH set $SERVICE_NAME AppEnvironmentExtra "PROTON_MCP_HTTP=1" "PROTON_MCP_HOST=$MCP_HOST" "PROTON_MCP_PORT=$MCP_PORT" | Out-Null

    & $NSSM_PATH set $SERVICE_NAME Start SERVICE_AUTO_START | Out-Null

    Write-Ok "Service '$SERVICE_NAME' installed (auto-start at boot)"
    Write-Info "Endpoint: http://${MCP_HOST}:${MCP_PORT}/mcp"
    Write-Info "Logs at: $LOG_FILE"
}

function Do-Uninstall {
    $status = Get-ServiceStatus
    if ($status -eq "not_installed") { Write-Warn "Service '$SERVICE_NAME' is not installed"; return }
    if ($status -eq "running") {
        Write-Info "Stopping service..."
        & $NSSM_PATH stop $SERVICE_NAME | Out-Null
        Start-Sleep -Seconds 2
    }
    Write-Info "Removing service '$SERVICE_NAME'..."
    & $NSSM_PATH remove $SERVICE_NAME confirm | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "NSSM remove failed with exit code $LASTEXITCODE" }
    Write-Ok "Service '$SERVICE_NAME' removed"
}

function Do-Start {
    $status = Get-ServiceStatus
    if ($status -eq "not_installed") { Write-Err "Service not installed. Run 'install' first."; return }
    if ($status -eq "running") { Write-Warn "Service is already running"; return }
    Write-Info "Starting service..."
    & $NSSM_PATH start $SERVICE_NAME | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "NSSM start failed with exit code $LASTEXITCODE" }
    Start-Sleep -Seconds 1
    $newStatus = Get-ServiceStatus
    if ($newStatus -eq "running") { Write-Ok "Service '$SERVICE_NAME' started" }
    else { Write-Warn "Service status: $newStatus (check logs at $LOG_FILE)" }
}

function Do-Stop {
    $status = Get-ServiceStatus
    if ($status -eq "not_installed") { Write-Err "Service '$SERVICE_NAME' is not installed"; return }
    if ($status -ne "running") { Write-Warn "Service is not running (status: $status)"; return }
    Write-Info "Stopping service..."
    & $NSSM_PATH stop $SERVICE_NAME | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "NSSM stop failed with exit code $LASTEXITCODE" }
    Write-Ok "Service '$SERVICE_NAME' stopped"
}

function Do-Status {
    $status = Get-ServiceStatus
    switch ($status) {
        "not_installed" { Write-Info "Service '$SERVICE_NAME' is not installed" }
        "running" {
            Write-Ok "Service '$SERVICE_NAME' is running"
            Write-Info "Endpoint: http://${MCP_HOST}:${MCP_PORT}/mcp"
            Write-Info "Logs: $LOG_FILE"
        }
        default {
            Write-Warn "Service '$SERVICE_NAME' status: $status"
            Write-Info "Logs: $LOG_FILE"
        }
    }
}

# ── Main ──────────────────────────────────────────────────────────────────────

switch ($Action) {
    "install"   { Do-Install }
    "uninstall" { Do-Uninstall }
    "start"     { Do-Start }
    "stop"      { Do-Stop }
    "status"    { Do-Status }
}
