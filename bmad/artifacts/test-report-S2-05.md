# Test Report — S2-05: Daemon entry point (main.py)

**Date:** 2026-05-07
**Result:** PASS — 8/8

```
tests/test_main.py::TestParseArgs::test_defaults PASSED
tests/test_main.py::TestParseArgs::test_custom_ports PASSED
tests/test_main.py::TestParseArgs::test_imap_only_flag PASSED
tests/test_main.py::TestParseArgs::test_smtp_only_flag PASSED
tests/test_main.py::TestConnectProton::test_success_on_first_attempt PASSED
tests/test_main.py::TestConnectProton::test_retry_on_failure_then_success PASSED
tests/test_main.py::TestConnectProton::test_exits_after_max_retries PASSED
tests/test_main.py::TestRunImap::test_imap_only_skips_smtp PASSED
8 passed in 0.13s
```

## Full suite

90/90 tests pass (Sprint 1 + Sprint 2 combined).
