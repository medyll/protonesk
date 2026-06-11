#!/usr/bin/env python3
"""
Pytest configuration — Mock proton module for tests

This allows tests to run without installing proton-python-client.
"""

import sys
from unittest.mock import MagicMock


class _ProtonAPIError(Exception):
    """Stand-in for proton.exceptions.ProtonAPIError (code/error attrs)."""

    def __init__(self, ret=None):
        ret = ret or {}
        self.code = ret.get("Code", "N/A")
        self.error = ret.get("Error", "N/A")
        self.headers = ret.get("Headers", "N/A")
        super().__init__(self.error)


# Mock proton module (not available in test environment)
proton_mock = MagicMock()
proton_mock.api = MagicMock()
proton_mock.api.Session = MagicMock()

exceptions_mock = MagicMock()
exceptions_mock.ProtonAPIError = _ProtonAPIError

sys.modules['proton'] = proton_mock
sys.modules['proton.api'] = proton_mock.api
sys.modules['proton.exceptions'] = exceptions_mock
