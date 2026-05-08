# Test Report — S4-01: Config multi-compte dans config.yaml

**Date:** 2026-05-07  
**Story:** S4-01  
**Sprint:** 4  

---

## Summary

| Metric | Value |
|--------|-------|
| Tests Run | 16 |
| Passed | 16 |
| Failed | 0 |
| Skipped | 0 |

**Result:** ✅ All tests passed

---

## Test Details

### Existing Tests (S3-04) — All Pass
- `test_defaults_when_no_file_no_args` — ✅
- `test_yaml_overrides_defaults` — ✅
- `test_cli_args_override_yaml` — ✅
- `test_missing_config_file_uses_defaults` — ✅
- `test_tls_flag_from_args` — ✅
- `test_tls_from_yaml` — ✅
- `test_invalid_yaml_falls_back_to_defaults` — ✅
- `test_log_level_from_yaml` — ✅
- `test_local_password_from_yaml` — ✅

### New Multi-Account Tests (S4-01) — All Pass
- `test_accounts_loaded_from_yaml` — ✅ Verifies `accounts` list is loaded and normalized
- `test_label_defaults_to_username` — ✅ Verifies label defaults to username when omitted
- `test_backward_compat_no_accounts_key` — ✅ Verifies single-account mode still works
- `test_empty_accounts_raises_error` — ✅ Verifies ConfigError on empty accounts list
- `test_accounts_not_list_raises_error` — ✅ Verifies ConfigError when accounts is not a list
- `test_account_missing_username_raises_error` — ✅ Verifies ConfigError on missing username
- `test_account_not_dict_raises_error` — ✅ Verifies ConfigError when account entry is not a dict

---

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `config.yaml` accepts clé `accounts` (liste de dicts) | ✅ |
| Chaque compte : `username`, `label` (optionnel, défaut = username) | ✅ |
| `load_config()` retourne `accounts` dans le dict mergé | ✅ |
| Rétrocompatible : si `accounts` absent → comportement actuel | ✅ |
| Validation : si `accounts` présent mais vide → erreur explicite | ✅ |

---

## Code Changes

- `src/config.py` — Added `_validate_accounts()`, `ConfigError`, multi-account support in `load_config()`
- `tests/test_config.py` — Added `TestMultiAccountConfig` class with 7 new tests
