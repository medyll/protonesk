<#
.SYNOPSIS
    Runs `hydroxide serve` in a restart loop, with rotating logs.

.DESCRIPTION
    Intended to be launched at user logon by a Scheduled Task
    (see install-hydroxide-service-windows.ps1). Not meant to be
    run interactively for normal use, except for debugging.
#>

$ErrorActionPreference = "Continue"

$LogDir = Join-Path $env:LOCALAPPDATA "Hydroxide\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogFile = Join-Path $LogDir "hydroxide.log"
$MaxLogBytes = 10MB

function Resolve-Hydroxide {
    $cmd = Get-Command hydroxide.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $goBin = Join-Path $env:USERPROFILE "go\bin\hydroxide.exe"
    if (Test-Path $goBin) { return $goBin }

    throw "hydroxide.exe not found in PATH or $goBin. Run: go install github.com/emersion/hydroxide/cmd/hydroxide@latest"
}

$hydroxide = Resolve-Hydroxide

while ($true) {
    if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt $MaxLogBytes)) {
        Move-Item -Path $LogFile -Destination "$LogFile.old" -Force
    }

    "[$(Get-Date -Format o)] starting: $hydroxide serve" | Add-Content -Path $LogFile
    & $hydroxide serve *>> $LogFile
    "[$(Get-Date -Format o)] hydroxide exited (code $LASTEXITCODE), restarting in 5s" | Add-Content -Path $LogFile

    Start-Sleep -Seconds 5
}
