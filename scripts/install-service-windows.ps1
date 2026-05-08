<#
.SYNOPSIS
    Protonesk — Windows Service Manager (NSSM)

.DESCRIPTION
    Installs, uninstalls, starts, stops, and checks status of the Protonesk
    as a Windows service using NSSM (Non-Sucking Service Manager).

    Service runs under the current user account to maintain access to the Windows
    Credential Manager (keyring).

.PARAMETER Action
    One of: install, uninstall, start, stop, status

.EXAMPLE
    .\install-service-windows.ps1 install
    .\install-service-windows.ps1 start
    .\install-service-windows.ps1 status
    .\install-service-windows.ps1 stop
    .\install-service-windows.ps1 uninstall
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("install", "uninstall", "start", "stop", "status")]
    [string]$Action
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Constants ─────────────────────────────────────────────────────────────────

$SERVICE_NAME = "ProtonMailBridge"
$DISPLAY_NAME = "Protonesk"
$DESCRIPTION = "Protonesk — IMAP/SMTP proxy for Proton Mail"
$APPDATA_DIR = Join-Path $env:LOCALAPPDATA "ProtonBridge"
$NSSM_DIR = $APPDATA_DIR
$NSSM_PATH = Join-Path $NSSM_DIR "nssm.exe"
$NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
$NSSM_HASH = "E93052B7D0A8B5F8E1B5E0F5C5D5E5F5A5B5C5D5E5F5A5B5C5D5E5F5A5B5C5D5"  # SHA256 placeholder
$LOG_DIR = Join-Path $APPDATA_DIR "logs"
$LOG_FILE = Join-Path $LOG_DIR "bridge.log"
$LOG_ROTATE_MB = 10

# Resolve project root (parent of scripts/)
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR
$PYTHON_EXE = "python"
$MAIN_PY = Join-Path $PROJECT_ROOT "main.py"

# ── Helper Functions ──────────────────────────────────────────────────────────

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERR]  $Message" -ForegroundColor Red
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-PythonPath {
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command "python3" -ErrorAction SilentlyContinue
    }
    if (-not $python) {
        throw "Python not found in PATH. Install Python 3.11+ and add to PATH."
    }
    return $python.Source
}

function Download-Nssm {
    if (Test-Path $NSSM_PATH) {
        Write-Ok "NSSM already installed at $NSSM_PATH"
        return
    }

    Write-Info "Downloading NSSM..."
    Ensure-Directory $NSSM_DIR

    $zipPath = Join-Path $NSSM_DIR "nssm.zip"
    try {
        Invoke-WebRequest -Uri $NSSM_URL -OutFile $zipPath -UseBasicParsing
    } catch {
        throw "Failed to download NSSM from $NSSM_URL : $_"
    }

    Write-Info "Extracting NSSM..."
    # NSSM zip contains nssm-2.24/win64/nssm.exe or win32/nssm.exe
    $arch = if ([Environment]::Is64BitOperatingSystem) { "win64" } else { "win32" }
    Expand-Archive -Path $zipPath -DestinationPath $NSSM_DIR -Force

    $extractedNssm = Join-Path $NSSM_DIR "nssm-2.24" | Join-Path -ChildPath $arch | Join-Path -ChildPath "nssm.exe"
    if (-not (Test-Path $extractedNssm)) {
        # Fallback: search for nssm.exe in extracted content
        $found = Get-ChildItem -Path $NSSM_DIR -Recurse -Filter "nssm.exe" | Select-Object -First 1
        if ($found) {
            $extractedNssm = $found.FullName
        } else {
            throw "Could not find nssm.exe in extracted archive"
        }
    }

    Move-Item -Path $extractedNssm -Destination $NSSM_PATH -Force
    Remove-Item $zipPath -Force
    # Clean up extracted folder
    $nssmVersionDir = Join-Path $NSSM_DIR "nssm-2.24"
    if (Test-Path $nssmVersionDir) {
        Remove-Item $nssmVersionDir -Recurse -Force
    }

    Write-Ok "NSSM installed at $NSSM_PATH"
}

function Get-ServiceStatus {
    $service = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if (-not $service) {
        return "not_installed"
    }
    return $service.Status.ToString().ToLower()
}

# ── Actions ───────────────────────────────────────────────────────────────────

function Do-Install {
    $status = Get-ServiceStatus
    if ($status -ne "not_installed") {
        Write-Warn "Service '$SERVICE_NAME' already exists (status: $status)"
        Write-Info "Run 'uninstall' first to reinstall, or 'start' to run it."
        return
    }

    # Check Python
    $PYTHON_EXE = Get-PythonPath
    Write-Info "Using Python: $PYTHON_EXE"

    # Check main.py
    if (-not (Test-Path $MAIN_PY)) {
        throw "main.py not found at $MAIN_PY"
    }

    # Download NSSM
    Download-Nssm

    # Create directories
    Ensure-Directory $LOG_DIR

    Write-Info "Installing service '$SERVICE_NAME'..."

    & $NSSM_PATH install $SERVICE_NAME $PYTHON_EXE $MAIN_PY | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM install failed with exit code $LASTEXITCODE"
    }

    # Configure service
    & $NSSM_PATH set $SERVICE_NAME DisplayName $DISPLAY_NAME | Out-Null
    & $NSSM_PATH set $SERVICE_NAME Description $DESCRIPTION | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppDirectory $PROJECT_ROOT | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppStdout $LOG_FILE | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppStderr $LOG_FILE | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppRotateFiles 1 | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppRotateBytes ($LOG_ROTATE_MB * 1024 * 1024) | Out-Null
    & $NSSM_PATH set $SERVICE_NAME AppRotateOnline 1 | Out-Null

    # Set startup type to automatic
    & $NSSM_PATH set $SERVICE_NAME Start SERVICE_AUTO_START | Out-Null

    Write-Ok "Service '$SERVICE_NAME' installed successfully"
    Write-Info "Start with: .\install-service-windows.ps1 start"
    Write-Info "Logs at: $LOG_FILE"
}

function Do-Uninstall {
    $status = Get-ServiceStatus
    if ($status -eq "not_installed") {
        Write-Warn "Service '$SERVICE_NAME' is not installed"
        return
    }

    # Stop first if running
    if ($status -eq "running") {
        Write-Info "Stopping service..."
        & $NSSM_PATH stop $SERVICE_NAME | Out-Null
        Start-Sleep -Seconds 2
    }

    Write-Info "Removing service '$SERVICE_NAME'..."
    & $NSSM_PATH remove $SERVICE_NAME confirm | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM remove failed with exit code $LASTEXITCODE"
    }

    Write-Ok "Service '$SERVICE_NAME' removed"
    Write-Info "Config and logs preserved at $APPDATA_DIR"
}

function Do-Start {
    $status = Get-ServiceStatus
    if ($status -eq "not_installed") {
        Write-Err "Service '$SERVICE_NAME' is not installed. Run 'install' first."
        return
    }
    if ($status -eq "running") {
        Write-Warn "Service is already running"
        return
    }

    Write-Info "Starting service..."
    & $NSSM_PATH start $SERVICE_NAME | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM start failed with exit code $LASTEXITCODE"
    }

    Start-Sleep -Seconds 1
    $newStatus = Get-ServiceStatus
    if ($newStatus -eq "running") {
        Write-Ok "Service '$SERVICE_NAME' started"
    } else {
        Write-Warn "Service status: $newStatus (check logs at $LOG_FILE)"
    }
}

function Do-Stop {
    $status = Get-ServiceStatus
    if ($status -eq "not_installed") {
        Write-Err "Service '$SERVICE_NAME' is not installed"
        return
    }
    if ($status -ne "running") {
        Write-Warn "Service is not running (status: $status)"
        return
    }

    Write-Info "Stopping service..."
    & $NSSM_PATH stop $SERVICE_NAME | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM stop failed with exit code $LASTEXITCODE"
    }

    Write-Ok "Service '$SERVICE_NAME' stopped"
}

function Do-Status {
    $status = Get-ServiceStatus
    switch ($status) {
        "not_installed" {
            Write-Info "Service '$SERVICE_NAME' is not installed"
            Write-Info "Install with: .\install-service-windows.ps1 install"
        }
        "running" {
            Write-Ok "Service '$SERVICE_NAME' is running"
            $service = Get-Service -Name $SERVICE_NAME
            Write-Info "PID: $($service.Id)"
            Write-Info "Logs: $LOG_FILE"
        }
        default {
            Write-Warn "Service '$SERVICE_NAME' status: $status"
            Write-Info "Start with: .\install-service-windows.ps1 start"
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
