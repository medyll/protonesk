# Test Report — S2-02: Serveur IMAP core

**Date:** 2026-05-07
**Result:** PASS — 14/14

```
tests/test_imap_server.py::test_greeting_on_connect PASSED
tests/test_imap_server.py::test_capability_command PASSED
tests/test_imap_server.py::test_noop_command PASSED
tests/test_imap_server.py::test_logout_command PASSED
tests/test_imap_server.py::test_login_success PASSED
tests/test_imap_server.py::test_login_failure PASSED
tests/test_imap_server.py::test_list_requires_auth PASSED
tests/test_imap_server.py::test_list_after_login PASSED
tests/test_imap_server.py::test_select_inbox PASSED
tests/test_imap_server.py::test_select_nonexistent_mailbox PASSED
tests/test_imap_server.py::test_fetch_requires_select PASSED
tests/test_imap_server.py::test_unknown_command_returns_bad PASSED
tests/test_imap_server.py::TestProtonIMAPServer::test_server_init PASSED
tests/test_imap_server.py::TestProtonIMAPServer::test_server_start_stop PASSED
14 passed in 0.07s
```
