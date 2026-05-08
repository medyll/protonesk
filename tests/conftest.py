#!/usr/bin/env python3
"""
Pytest configuration — Mock proton module for tests

This allows tests to run without installing proton-python-client.
"""

import sys
from unittest.mock import MagicMock

# Mock proton module (not available in test environment)
proton_mock = MagicMock()
proton_mock.session = MagicMock()
proton_mock.session.ProtonSession = MagicMock()

sys.modules['proton'] = proton_mock
sys.modules['proton.session'] = proton_mock.session
sys.modules['proton.api'] = proton_mock.api
