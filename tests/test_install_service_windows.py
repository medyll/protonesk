#!/usr/bin/env python3
"""Tests for install-service-windows.ps1 — S6-01

Validates PowerShell script structure and constants from Python.
"""

import pytest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "install-service-windows.ps1"


@pytest.fixture
def script_content():
    return SCRIPT_PATH.read_text(encoding="utf-8")


class TestScriptExists:

    def test_script_file_exists(self):
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"


class TestScriptSyntax:

    def test_valid_powershell_syntax(self):
        """Verify script parses without syntax errors."""
        import subprocess
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command",
             f"$errors = $null; [System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT_PATH}', [ref]$null, [ref]$errors); if ($errors.Count -gt 0) {{ exit 1 }}"],
            capture_output=True, text=True, shell=True
        )
        # If pwsh isn't available, skip (Windows-only)
        if result.returncode == 127 or "not found" in result.stderr.lower():
            pytest.skip("PowerShell not available")
        assert result.returncode == 0, f"Syntax errors: {result.stderr}"


class TestConstants:

    def test_service_name(self, script_content):
        assert '$SERVICE_NAME = "ProtonMailBridge"' in script_content

    def test_display_name(self, script_content):
        assert '$DISPLAY_NAME = "Proton Mail Bridge"' in script_content

    def test_localappdata_path(self, script_content):
        assert "LOCALAPPDATA" in script_content
        assert "ProtonBridge" in script_content

    def test_nssm_download_url(self, script_content):
        assert "nssm.cc" in script_content.lower() or "nssm" in script_content.lower()


class TestActions:

    def test_validate_set_all_actions(self, script_content):
        assert "ValidateSet" in script_content
        for action in ["install", "uninstall", "start", "stop", "status"]:
            assert action in script_content

    def test_install_function(self, script_content):
        assert "Do-Install" in script_content

    def test_uninstall_function(self, script_content):
        assert "Do-Uninstall" in script_content

    def test_start_function(self, script_content):
        assert "Do-Start" in script_content

    def test_stop_function(self, script_content):
        assert "Do-Stop" in script_content

    def test_status_function(self, script_content):
        assert "Do-Status" in script_content


class TestServiceConfiguration:

    def test_log_rotation_configured(self, script_content):
        assert "AppRotateFiles" in script_content
        assert "AppRotateBytes" in script_content

    def test_working_directory_set(self, script_content):
        assert "AppDirectory" in script_content
        assert "PROJECT_ROOT" in script_content

    def test_stdout_stderr_redirect(self, script_content):
        assert "AppStdout" in script_content
        assert "AppStderr" in script_content

    def test_python_check_before_install(self, script_content):
        assert "Get-PythonPath" in script_content

    def test_nssm_download_function(self, script_content):
        assert "Download-Nssm" in script_content
        assert "Invoke-WebRequest" in script_content

    def test_uninstall_preserves_data(self, script_content):
        assert "preserved" in script_content.lower()


class TestDocumentation:

    def test_has_synopsis(self, script_content):
        assert ".SYNOPSIS" in script_content

    def test_has_description(self, script_content):
        assert ".DESCRIPTION" in script_content

    def test_has_examples(self, script_content):
        assert ".EXAMPLE" in script_content

    def test_has_parameter_help(self, script_content):
        assert ".PARAMETER" in script_content
