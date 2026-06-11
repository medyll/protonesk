<#
.SYNOPSIS
    Protonesk - hydroxide Windows auto-start manager (Scheduled Task)

.DESCRIPTION
    hydroxide (https://github.com/emersion/hydroxide) is a third-party
    IMAP/SMTP/CardDAV bridge for ProtonMail that works with free accounts.
    This script registers `hydroxide serve` as a per-user Scheduled Task
    that starts at logon, with logs and a restart loop.

    No admin rights required (per-user logon task).

.PARAMETER Action
    One of: auth, install, uninstall, start, stop, status

.PARAMETER Username
    Your ProtonMail address. Required for the 'auth' action.

.EXAMPLE
    .\install-hydroxide-service-windows.ps1 auth -Username you@proton.me
    .\install-hydroxide-service-windows.ps1 install
    .\install-hydroxide-service-windows.ps1 start
    .\install-hydroxide-service-windows.ps1 status
    .\install-hydroxide-service-windows.ps1 stop
    .\install-hydroxide-service-windows.ps1 uninstall
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("auth", "install", "uninstall", "start", "stop", "status")]
    [string]$Action,

    [string]$Username
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Constants -----------------------------------------------------------------

$TASK_NAME = "Hydroxide"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RUNNER = Join-Path $SCRIPT_DIR "hydroxide-runner.ps1"
$LOG_DIR = Join-Path $env:LOCALAPPDATA "Hydroxide\logs"
$LOG_FILE = Join-Path $LOG_DIR "hydroxide.log"
$CONFIG_DIR = Join-Path $env:APPDATA "hydroxide"

# -- Helpers -------------------------------------------------------------------

function Write-Info { param([string]$m) Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok   { param([string]$m) Write-Host "[OK]   $m" -ForegroundColor Green }
function Write-Warn { param([string]$m) Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err  { param([string]$m) Write-Host "[ERR]  $m" -ForegroundColor Red }

function Resolve-Hydroxide {
    $cmd = Get-Command hydroxide.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $goBin = Join-Path $env:USERPROFILE "go\bin\hydroxide.exe"
    if (Test-Path $goBin) { return $goBin }

    return $null
}

function Test-Authenticated {
    return Test-Path (Join-Path $CONFIG_DIR "auth.json")
}

# -- Actions -------------------------------------------------------------------

function Do-Auth {
    if (-not $Username) {
        throw "Usage: .\install-hydroxide-service-windows.ps1 auth -Username you@proton.me"
    }

    $hydroxide = Resolve-Hydroxide
    if (-not $hydroxide) {
        throw "hydroxide.exe not found. Install it first: go install github.com/emersion/hydroxide/cmd/hydroxide@latest"
    }

    Write-Info "Logging in to ProtonMail as $Username..."
    Write-Info "You'll be prompted for your Proton password and 2FA code (if enabled)."
    & $hydroxide auth $Username
    if ($LASTEXITCODE -ne 0) {
        throw "hydroxide auth failed with exit code $LASTEXITCODE"
    }

    Write-Ok "Authenticated. hydroxide printed a BRIDGE PASSWORD above -"
    Write-Ok "use that (not your Proton password) in your email client."
    Write-Info "Next: .\install-hydroxide-service-windows.ps1 install"
}

function Do-Install {
    $hydroxide = Resolve-Hydroxide
    if (-not $hydroxide) {
        throw "hydroxide.exe not found. Install it first: go install github.com/emersion/hydroxide/cmd/hydroxide@latest"
    }

    if (-not (Test-Authenticated)) {
        Write-Err "Not authenticated yet (no $CONFIG_DIR\auth.json)."
        Write-Info "Run first: .\install-hydroxide-service-windows.ps1 auth -Username you@proton.me"
        return
    }

    $existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Warn "Scheduled task '$TASK_NAME' already exists."
        Write-Info "Run 'uninstall' first to reinstall, or 'start' to run it."
        return
    }

    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null

    Write-Info "Registering scheduled task '$TASK_NAME' (runs at logon)..."

    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$RUNNER`""

    $trigger = New-ScheduledTaskTrigger -AtLogOn

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Days 0) `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    Register-ScheduledTask -TaskName $TASK_NAME -Action $action -Trigger $trigger `
        -Settings $settings -Description "hydroxide IMAP/SMTP/CardDAV bridge for ProtonMail" | Out-Null

    Write-Ok "Task '$TASK_NAME' registered (starts at logon)."
    Write-Info "Start now with: .\install-hydroxide-service-windows.ps1 start"
    Write-Info "Logs at: $LOG_FILE"
}

function Do-Uninstall {
    $existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Warn "Scheduled task '$TASK_NAME' is not installed."
        return
    }

    Do-Stop

    Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
    Write-Ok "Task '$TASK_NAME' removed."
    Write-Info "Config ($CONFIG_DIR) and logs ($LOG_DIR) preserved."
}

function Do-Start {
    $existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Err "Task '$TASK_NAME' is not installed. Run 'install' first."
        return
    }

    Start-ScheduledTask -TaskName $TASK_NAME
    Start-Sleep -Seconds 1
    Do-Status
}

function Do-Stop {
    $existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if ($existing) {
        Stop-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    }

    # The runner loop spawns hydroxide.exe as a child; stop it explicitly too.
    Get-Process -Name "hydroxide" -ErrorAction SilentlyContinue | Stop-Process -Force

    Write-Ok "Stopped."
}

function Do-Status {
    $existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Info "Task '$TASK_NAME' is not installed."
        Write-Info "Install with: .\install-hydroxide-service-windows.ps1 install"
        return
    }

    $info = Get-ScheduledTaskInfo -TaskName $TASK_NAME
    Write-Info "Task '$TASK_NAME' state: $($existing.State)"
    Write-Info "Last run: $($info.LastRunTime)  Last result: $($info.LastTaskResult)"

    $proc = Get-Process -Name "hydroxide" -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Ok "hydroxide.exe is running (PID $($proc.Id -join ', '))"
    } else {
        Write-Warn "hydroxide.exe is not currently running"
    }

    Write-Info "Logs: $LOG_FILE"
    Write-Info "Config: $CONFIG_DIR"
}

# -- Main ----------------------------------------------------------------------

switch ($Action) {
    "auth"      { Do-Auth }
    "install"   { Do-Install }
    "uninstall" { Do-Uninstall }
    "start"     { Do-Start }
    "stop"      { Do-Stop }
    "status"    { Do-Status }
}
