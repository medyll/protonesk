# Tests for install-service-windows.ps1 — S6-01
# Validates script structure, syntax, and constants

$ScriptPath = Join-Path $PSScriptRoot "..\scripts\install-service-windows.ps1"

Describe "install-service-windows.ps1" {

    BeforeAll {
        $ScriptContent = Get-Content $ScriptPath -Raw
    }

    It "Script file exists" {
        Test-Path $ScriptPath | Should -BeTrue
    }

    It "Script has valid PowerShell syntax" {
        $errors = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile(
            $ScriptPath, [ref]$null, [ref]$errors
        )
        $errors | Should -BeNullOrEmpty
    }

    It "Defines SERVICE_NAME constant" {
        $ScriptContent | Should -Match '\$SERVICE_NAME\s*=\s*"ProtonMailBridge"'
    }

    It "Defines DISPLAY_NAME constant" {
        $ScriptContent | Should -Match '\$DISPLAY_NAME\s*=\s*"Proton Mail Bridge"'
    }

    It "Uses LOCALAPPDATA for NSSM directory" {
        $ScriptContent | Should -Match 'LOCALAPPDATA.*ProtonBridge'
    }

    It "Supports all required actions" {
        $ScriptContent | Should -Match 'ValidateSet.*install.*uninstall.*start.*stop.*status'
    }

    It "Configures log rotation" {
        $ScriptContent | Should -Match 'AppRotateFiles'
        $ScriptContent | Should -Match 'AppRotateBytes'
    }

    It "Sets working directory to project root" {
        $ScriptContent | Should -Match 'AppDirectory.*PROJECT_ROOT'
    }

    It "Redirects stdout and stderr to log file" {
        $ScriptContent | Should -Match 'AppStdout.*LOG_FILE'
        $ScriptContent | Should -Match 'AppStderr.*LOG_FILE'
    }

    It "Has install function" {
        $ScriptContent | Should -Match 'function\s+Do-Install'
    }

    It "Has uninstall function" {
        $ScriptContent | Should -Match 'function\s+Do-Uninstall'
    }

    It "Has start function" {
        $ScriptContent | Should -Match 'function\s+Do-Start'
    }

    It "Has stop function" {
        $ScriptContent | Should -Match 'function\s+Do-Stop'
    }

    It "Has status function" {
        $ScriptContent | Should -Match 'function\s+Do-Status'
    }

    It "Checks for Python before install" {
        $ScriptContent | Should -Match 'Get-PythonPath'
    }

    It "Downloads NSSM if not present" {
        $ScriptContent | Should -Match 'Download-Nssm'
        $ScriptContent | Should -Match 'Invoke-WebRequest.*nssm'
    }

    It "Uninstall preserves config and logs" {
        $ScriptContent | Should -Match 'preserved.*APPDATA_DIR|config.*logs.*preserved'
    }

    It "Has proper help documentation" {
        $ScriptContent | Should -Match '<#.*\.SYNOPSIS'
        $ScriptContent | Should -Match '\.EXAMPLE'
    }
}
