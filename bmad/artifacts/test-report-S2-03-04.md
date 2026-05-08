# Test Report — S2-03 + S2-04: IMAP Bridge (mapping + fetch/decrypt)

**Date:** 2026-05-07
**Result:** PASS — 19/19

```
tests/test_imap_bridge.py::TestAuth::test_correct_password PASSED
tests/test_imap_bridge.py::TestAuth::test_wrong_password PASSED
tests/test_imap_bridge.py::TestMailboxes::test_get_mailboxes_from_labels PASSED
tests/test_imap_bridge.py::TestMailboxes::test_get_mailboxes_cached PASSED
tests/test_imap_bridge.py::TestMailboxes::test_get_mailboxes_fallback_on_error PASSED
tests/test_imap_bridge.py::TestMailboxes::test_get_mailbox_status_inbox PASSED
tests/test_imap_bridge.py::TestMailboxes::test_get_mailbox_status_unknown PASSED
tests/test_imap_bridge.py::TestMailboxes::test_get_mailbox_status_cached PASSED
tests/test_imap_bridge.py::TestSeqMapping::test_seq_to_proton_id PASSED
tests/test_imap_bridge.py::TestSeqMapping::test_seq_out_of_range PASSED
tests/test_imap_bridge.py::TestSeqMapping::test_proton_flags_unread PASSED
tests/test_imap_bridge.py::TestSeqMapping::test_proton_flags_read PASSED
tests/test_imap_bridge.py::TestFetch::test_fetch_rfc822_format PASSED
tests/test_imap_bridge.py::TestFetch::test_fetch_decrypt_failure_placeholder PASSED
tests/test_imap_bridge.py::TestFetch::test_fetch_cached PASSED
tests/test_imap_bridge.py::TestFetch::test_handle_fetch_message_not_found PASSED
tests/test_imap_bridge.py::TestFetch::test_handle_fetch_bad_seq PASSED
tests/test_imap_bridge.py::TestStore::test_handle_store_ok PASSED
tests/test_imap_bridge.py::TestStore::test_handle_store_invalidates_cache PASSED
19 passed in 0.08s
```
