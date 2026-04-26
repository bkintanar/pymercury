# Feature: Full Codebase Audit + ~100% Test Coverage

## Summary

Read every source file in `pymercury/`, fix the 15 bugs uncovered by the audit (5 critical, 10 high), and lift line + branch coverage from the current ~32% to ~100% with ~95 new pytest tests. Standardize HTTP mocking on `requests-mock`, JWT/datetime fakes via `freezegun`, gate CI with `--cov-fail-under=100`. Delete the 1409-line dead-code file `pymercury/api/client_backup.py` (it alone accounts for 647 of the 1273 missed lines).

## User Story

As a maintainer of the pymercury SDK
I want every code path exercised by tests and every audit finding fixed
So that releases are trustworthy, regressions surface immediately, and I can refactor without fear.

## Problem Statement

- The library claims 1.0.5 production-stable but `__version__ = "1.0.0"`.
- 150 tests pass, but coverage is only ~32%; most tests verify imports/instantiation, not behavior.
- The full OAuth flow (`MercuryOAuthClient.authenticate`, B2C, refresh) is not exercised by any test.
- `MercuryOAuthClient.login_or_refresh` calls `self.login()` — a method that does not exist (`AttributeError` at runtime on every fall-through path).
- `OAuthTokens.__init__` recomputes `expires_at = datetime.now() + expires_in` on load, defeating `save_tokens`/`load_tokens` persistence.
- `_follow_redirects_for_code` uses the wrong `requests.Session`, breaking multi-hop OAuth redirects.
- Two production secrets (`client_id`, `api_subscription_key`) are hardcoded in `config.py`.
- `client_backup.py` (1409 lines) is dead code duplicating those secrets.

## Solution Statement

Two-track plan executed in order:

1. **Bug-fix track** — 15 ranked fixes, each with an immediate failing test that reproduces it, then the fix, then assert green.
2. **Coverage track** — add tests module-by-module until `pytest --cov=pymercury --cov-branch --cov-fail-under=100` passes. Standardize on `requests-mock` for HTTP, `freezegun` for time, `monkeypatch.setenv` + `importlib.reload` for module-import-time config tests.

## Metadata

| Field            | Value |
| ---------------- | ----- |
| Type             | BUG_FIX + ENHANCEMENT (test coverage) |
| Complexity       | HIGH (multi-step OAuth flow + ~95 new tests) |
| Systems Affected | `pymercury/` (all modules), `tests/` (all modules), `pyproject.toml`, `requirements-dev.txt`, `MANIFEST.in`, `.env.template` |
| Dependencies     | `pytest-cov>=7.1`, `requests-mock>=1.12`, `freezegun>=1.5`, `coverage>=7.13` |
| Estimated Tasks  | 28 (3 setup + 15 bug fixes + 9 test modules + 1 CI gate) |

---

## UX Design

This is a developer-experience change; "user" = library maintainer running tests.

### Before State

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              BEFORE STATE                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐            ║
║   │  Developer  │ ──────► │ run_tests.py│ ──────► │  150 PASS   │            ║
║   └─────────────┘         └─────────────┘         └─────────────┘            ║
║                                                          │                    ║
║                                                          ▼                    ║
║                                                  ┌─────────────────┐          ║
║                                                  │ False confidence│          ║
║                                                  │ 32% real cover  │          ║
║                                                  │ OAuth untested  │          ║
║                                                  │ 15 latent bugs  │          ║
║                                                  └─────────────────┘          ║
║                                                                               ║
║   PAIN: AttributeError on smart-login fallback in production                  ║
║   PAIN: persisted tokens silently lose expiry                                 ║
║   PAIN: refactors break things tests don't cover                              ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### After State

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                               AFTER STATE                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────┐    ┌──────────────────┐    ┌────────────────────────┐      ║
║   │  Developer  │───►│ pytest --cov     │───►│ 245+ tests, 100% line/ │      ║
║   │             │    │ --cov-branch     │    │ branch, gated by CI    │      ║
║   └─────────────┘    │ --cov-fail-under │    └────────────────────────┘      ║
║                      │ =100             │                │                    ║
║                      └──────────────────┘                ▼                    ║
║                                                  ┌─────────────────┐          ║
║                                                  │ 15 bugs fixed   │          ║
║                                                  │ OAuth flow      │          ║
║                                                  │   mocked end-to-│          ║
║                                                  │   end           │          ║
║                                                  │ Token persist   │          ║
║                                                  │   round-trips   │          ║
║                                                  │ client_backup.py│          ║
║                                                  │   deleted       │          ║
║                                                  └─────────────────┘          ║
║                                                                               ║
║   VALUE: regressions caught immediately, refactors safe, CI gate enforces it  ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes

| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `pymercury/__init__.py:97` | `__version__ = "1.0.0"` | `__version__ = "1.0.5"` | `pymercury.__version__` reflects reality |
| `pymercury/oauth/client.py:486` | `return self.login(email, password)` (AttributeError) | `return self.authenticate()` | Smart-login fall-through works |
| `pymercury/oauth/client.py:33-42` | `OAuthTokens` recomputes expires_at on load | Honors saved `expires_at` ISO string | `load_tokens()` preserves real expiry |
| `pymercury/api/client.py:409,581,639` | `'today' in locals()` antipattern | Explicit sentinel | Code-readers no longer mystified |
| `pymercury/api/client_backup.py` | 1409-line dead duplicate with secrets | DELETED | Smaller checkout, no secret duplication |
| `pyproject.toml` | No pytest/coverage section | Full `[tool.pytest.ini_options]` + `[tool.coverage.*]` | `pytest` alone runs coverage + 100% gate |
| Running tests | `python run_tests.py` | `pytest` (run_tests.py kept as wrapper) | Standard pytest UX |

---

## Mandatory Reading

**CRITICAL: Implementation agent MUST read these files before starting any task:**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `pymercury/oauth/client.py` | 1-486 | Full OAuth flow — most coverage gaps + 3 of 5 critical bugs live here |
| P0 | `pymercury/api/client.py` | 1-847 | All API methods — error-path tests must mirror current `_make_request` exception mapping |
| P0 | `pymercury/client.py` | 1-407 | `MercuryClient` orchestration + token persistence (HIGH-4 bug) |
| P0 | `pymercury/utils.py` | all | `parse_mercury_json` regex (HIGH-3 bug), `decode_jwt_payload` padding |
| P0 | `pymercury/config.py` | all | Module-import-time `default_config` side-effect, `int(os.getenv(...))` ValueError (CRITICAL-4) |
| P1 | `pymercury/api/endpoints.py` | 1-123 | Two `service_usage` definitions, dead stubs |
| P1 | `pymercury/api/models/billing.py` | all | `MeterInfo` + `BillSummary` — 7% covered, statement-detail line-item parser |
| P1 | `pymercury/api/models/electricity.py` | all | 4 untested classes; HIGH-6 fabricated meter readings; HIGH-7 fabricated GST |
| P1 | `pymercury/api/models/base.py` | 1-94 | `ServiceUsage` — pattern for all usage model tests |
| P2 | `tests/test_api_client.py` | 1-100 | Existing mocking pattern (`patch('requests.Session.request')`) — the new `requests-mock` pattern replaces it for new tests |
| P2 | `tests/test_utilities.py` | all | Existing pattern for utility tests; `decode_jwt_payload` test currently swallows the failure path |
| P2 | `tests/test_models_account.py` | all | Existing model-test pattern to mirror for billing/electricity |
| P3 | `mercury_examples.py` | 38-100 | Real-world usage shapes; the `get_complete_data` happy path |

**External Documentation:**
| Source | Section | Why Needed |
|--------|---------|------------|
| [Coverage.py 7.13 Config Reference](https://coverage.readthedocs.io/en/latest/config.html) | `[tool.coverage.run]` and `[tool.coverage.report]` | `omit`, `branch`, `exclude_also` (NOT `exclude_lines`) |
| [Coverage.py — Excluding Code](https://coverage.readthedocs.io/en/latest/excluding.html) | `# pragma: no cover` + `exclude_also` | Exclude legacy stub `service_usage` (shadowed) and dead `else: return None` branches |
| [pytest-cov 7.1 Config](https://pytest-cov.readthedocs.io/en/latest/config.html) | `addopts` with `--cov` flags | Gate CI with `--cov-fail-under=100` |
| [requests-mock pytest fixture](https://requests-mock.readthedocs.io/en/latest/pytest.html) | `requests_mock` fixture | Replace `unittest.mock.patch('requests.Session.request')` |
| [requests-mock Creating Responses](https://requests-mock.readthedocs.io/en/latest/response.html) | `exc=` parameter, sequential responses | `exc=requests.exceptions.ConnectionError(...)` for connection-error path; sequential list `[{...}, {...}]` for the 6-step OAuth flow |
| [freezegun GitHub](https://github.com/spulec/freezegun) | `@freeze_time` decorator | Mock `datetime.now()` in `OAuthTokens.__init__` for expiry tests |
| [pytest monkeypatch — env vars](https://docs.pytest.org/en/stable/how-to/monkeypatch.html#monkeypatch-setenv) | `monkeypatch.setenv` + `delenv` | Test `MercuryConfig._validate` branches by clearing env vars |

---

## Patterns to Mirror

**TEST_FILE_HEADER (existing):**
```python
# SOURCE: tests/test_models_account.py:1-15
"""
Tests for Account models in pymercury library
"""

import pytest
from pymercury.api.models import Account, CustomerInfo, Service, ServiceIds


class TestCustomerInfo:
    """Test cases for CustomerInfo model"""

    def test_customer_info_creation(self):
        """Test creating CustomerInfo with valid data"""
```

**MOCKING_PATTERN_LEGACY (existing — `unittest.mock`):**
```python
# SOURCE: tests/test_api_client.py:42-48
@patch('requests.Session.request')
def test_successful_request(self, mock_request, mock_client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'test': 'data'}
    mock_request.return_value = mock_response
```

**MOCKING_PATTERN_NEW (target — `requests-mock`):**
```python
# NEW PATTERN — use this for all new tests touching HTTP
def test_get_customer_info_success(requests_mock):
    requests_mock.get(
        "https://apis.mercury.co.nz/selfservice/v1/customers/cust-1",
        json={"customerId": "cust-1", "name": "Test", "email": "t@example.com"},
    )
    api = MercuryAPIClient("dummy_token")
    info = api.get_customer_info("cust-1")
    assert info.customer_id == "cust-1"

def test_get_customer_info_connection_error(requests_mock):
    requests_mock.get(
        "https://apis.mercury.co.nz/selfservice/v1/customers/cust-1",
        exc=requests.exceptions.ConnectionError("DNS failed"),
    )
    api = MercuryAPIClient("dummy_token")
    with pytest.raises(MercuryAPIConnectionError):
        api.get_customer_info("cust-1")
```

**ERROR_HIERARCHY_TEST (existing):**
```python
# SOURCE: tests/test_error_handling.py — mirror this exact assertion style
def test_unauthorized_maps_to_specific_exception(requests_mock):
    requests_mock.get(
        "https://apis.mercury.co.nz/selfservice/v1/customers/c1",
        status_code=401,
    )
    api = MercuryAPIClient("dummy_token")
    with pytest.raises(MercuryAPIUnauthorizedError):  # NOT bare Exception
        api.get_customer_info("c1")
```

**MODEL_TEST (existing — mirror for billing/electricity):**
```python
# SOURCE: tests/test_models_account.py:11-40
class TestCustomerInfo:
    def test_creation_with_full_data(self):
        data = {"customerId": "cust1", "name": "John", "email": "j@x.com"}
        info = CustomerInfo(data)
        assert info.customer_id == "cust1"
        assert info.name == "John"
        assert info.email == "j@x.com"
        assert info.raw_data == data

    def test_creation_with_missing_fields(self):
        info = CustomerInfo({})
        assert info.customer_id is None
        assert info.name is None
        assert info.email is None
```

**FAKE_JWT_HELPER (NEW — to be created in `tests/conftest.py`):**
```python
# tests/conftest.py — NEW FILE
import base64, json, pytest

def _fake_jwt(payload: dict | None = None) -> str:
    """Build minimal unsigned JWT — pymercury decodes without verification."""
    header = {"alg": "RS256", "typ": "JWT"}
    body = payload or {
        "extension_customerId": "cust-test",
        "email": "test@example.com",
        "given_name": "Test",
        "family_name": "User",
        "exp": 9999999999,
    }
    def _b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{_b64(header)}.{_b64(body)}.fakesignature"


@pytest.fixture
def fake_jwt():
    return _fake_jwt


@pytest.fixture
def fake_oauth_token_data(fake_jwt):
    return {
        "access_token": fake_jwt(),
        "refresh_token": "rt_test_123",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
```

**CONFIG_RELOAD_PATTERN (NEW):**
```python
# tests/test_configuration.py
import importlib
import pytest

def test_invalid_timeout_env_raises(monkeypatch):
    monkeypatch.setenv("MERCURY_TIMEOUT", "not-an-integer")
    import pymercury.config as cfg_mod
    with pytest.raises(MercuryConfigError):  # after CRITICAL-4 fix
        importlib.reload(cfg_mod)

@pytest.fixture(autouse=True)
def restore_default_config():
    import pymercury.config as cfg_mod
    original = cfg_mod.default_config
    yield
    cfg_mod.default_config = original
```

**FREEZEGUN_PATTERN (NEW):**
```python
from freezegun import freeze_time

@freeze_time("2026-01-01 12:00:00")
def test_token_not_yet_expired(fake_oauth_token_data):
    tokens = OAuthTokens(fake_oauth_token_data)
    assert not tokens.is_expired()

def test_token_expired_after_window(fake_oauth_token_data):
    with freeze_time("2026-01-01 12:00:00"):
        tokens = OAuthTokens(fake_oauth_token_data)
    with freeze_time("2026-01-01 13:00:01"):  # 1s past expiry
        assert tokens.is_expired()
```

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `pymercury/api/client_backup.py` | DELETE | Dead code; 1409 lines; never imported; duplicates secrets (HIGH-1) |
| `pymercury/__init__.py` | UPDATE | Fix `__version__` → "1.0.5" (CRITICAL-5) |
| `pymercury/oauth/client.py` | UPDATE | Fix `self.login` → `self.authenticate` (CRITICAL-1); fix session in redirects (CRITICAL-3); fix `expires_at` reload (HIGH-4); tighten bare except (HIGH-8); fix verbose logging of credentials (HIGH-9) |
| `pymercury/config.py` | UPDATE | Catch ValueError on int(env) → `MercuryConfigError` (CRITICAL-4); externalize `client_id` & `api_subscription_key` defaults (HIGH-11) |
| `pymercury/api/client.py` | UPDATE | Replace `'today'/'yesterday' in locals()` antipattern (HIGH-10); remove unreachable `else: return None` branches (HIGH-5) |
| `pymercury/api/endpoints.py` | UPDATE | Delete shadowed 2-arg `service_usage` stub at lines 43-45 (CRITICAL-2); decide on `account_bills` (line 39) and `service_meter_readings` (line 47) — delete or implement |
| `pymercury/api/models/electricity.py` | UPDATE | Set `previous_reading_value`/`consumption_kwh` to `None` not fabricated 100 (HIGH-6); set `daily_fixed_charge`/`gst_amount` to `None` not 30%/15% estimates (HIGH-7) |
| `pymercury/utils.py` | UPDATE | Make `parse_mercury_json` try `json.loads` first then fall back to regex (HIGH-3) |
| `pymercury/api/models/broadband.py` | UPDATE | Remove dead inner `else` at lines 47-49 (logically unreachable) |
| `pyproject.toml` | UPDATE | Add `[tool.pytest.ini_options]` and `[tool.coverage.*]`; bump `version = "1.0.5"` consistency; drop py3.7 from optional-deps if `freezegun>=1.5` requires py3.8+ |
| `requirements-dev.txt` | UPDATE | Add `requests-mock>=1.12`, `freezegun>=1.5`, pin `pytest-cov>=7.1`, `coverage>=7.13` |
| `MANIFEST.in` | UPDATE | Remove reference to non-existent `test_mercury_library.py` |
| `.env.template` | UPDATE | Document all 10 env vars (currently only 2) |
| `tests/conftest.py` | CREATE | Fake-JWT factory, `fake_oauth_token_data` fixture, `default_config` restore fixture |
| `tests/test_utilities.py` | UPDATE | Add tests for `extract_from_html` (success + ValueError), `parse_mercury_json` (3 paths), `extract_auth_code_from_url` (2 paths), `decode_jwt_payload` error branches |
| `tests/test_configuration.py` | UPDATE | Add 10 `_validate` branch tests; add `MERCURY_TIMEOUT=abc` reload test (CRITICAL-4 reproducer); add `dotenv` import-fallback test via `monkeypatch.setattr('builtins.__import__', ...)` |
| `tests/test_oauth_client.py` | CREATE | Full OAuth flow tests using `requests_mock` — 6-step PKCE; refresh success/failure/exception; `OAuthTokens` field/property tests; `is_expired`/`expires_soon`/`time_until_expiry` via `freezegun`; `login_or_refresh` 3 branches (CRITICAL-1 reproducer) |
| `tests/test_api_client.py` | UPDATE | Migrate to `requests_mock`; add 429 (rate limit) and 500 (generic 4xx/5xx) status tests; fix the connection-error test to use `requests.exceptions.ConnectionError` (currently uses bare `Exception`); add tests for every untested method (`get_electricity_meter_info`, `get_bill_summary`, `get_usage_content`, `get_service_usage`, `get_electricity_summary`, `get_electricity_plans`, `get_electricity_meter_reads`, plus the explicit-`end_date` branches that exercise the post-fix `'today' in locals()` replacement); remove unreachable-else assertions |
| `tests/test_client.py` | CREATE | `MercuryClient` orchestration tests with mocked `MercuryOAuthClient` and `MercuryAPIClient`; `CompleteAccountData` properties; `save_tokens`/`load_tokens` round-trip tests (HIGH-4 reproducer using `freezegun` to advance time across save/load); `authenticate()` and `get_complete_data()` convenience-function tests |
| `tests/test_models_billing.py` | CREATE | `MeterInfo` (electricity_meter found + not-found branches); `BillSummary` (statement-detail loop with electricity/gas/broadband line items, empty statement) |
| `tests/test_models_electricity.py` | CREATE | `ElectricityUsageContent`, `ElectricitySummary` (weekly_usage present + empty), `ElectricityPlans` (Daily Fixed Charge + Anytime rate + missing), `ElectricityMeterReads` (list/dict input, empty registers, non-numeric latest_reading) |
| `tests/test_endpoints.py` | UPDATE | Add tests for `account_bills`, `service_meter_readings` (or delete those endpoints if dropped); cover the 7-arg `service_usage` happy path and edge cases for query-string encoding |

---

## NOT Building (Scope Limits)

Explicit exclusions to prevent scope creep:

- **Real network tests / contract tests against live Mercury API.** Out of scope; would be flaky and require credentials. All HTTP interactions are mocked.
- **OAuth token refresh on a real Azure B2C tenant.** Mocked only.
- **Type-checking (`mypy`) cleanup.** This plan does not retrofit type annotations; the existing partial typing is preserved. Run `mypy` separately if desired.
- **`black`/`flake8` reformat of the whole tree.** Touch only files we edit; do not reflow unrelated code.
- **Refactoring `MercuryAPIClient` into smaller modules.** It is 847 lines but functional; coverage and bug fixes do not require splitting it.
- **Changes to `mercury_examples.py`.** It is documentation/example code, not part of the tested surface. Do not change beyond what's needed for `pymercury.__version__` consistency.
- **Changes to `deploy.py` / `deploy.sh`.** Out of scope.
- **Adding new SDK features** (e.g., async support, retries, connection pooling tuning). Bug fixes and tests only.
- **Implementing the `account_bills` and `service_meter_readings` endpoint stubs** as real working calls. Decision: delete them as dead code unless the maintainer signals they are needed (recommend delete; surface in Notes).
- **Hard-deleting the `client_id` and `api_subscription_key` defaults from `config.py` in this plan.** Documented as HIGH-11 but flagged for separate discussion — these may be intentional public B2C app credentials. Plan only externalizes them via env vars without removing the defaults; full removal is a follow-up.

---

## Step-by-Step Tasks

Execute in order. Each task is atomic and independently verifiable.

### Phase A — Setup (Tasks 1-3)

#### Task 1: Set up dev environment

- **ACTION**: Create venv and install dev deps.
- **IMPLEMENT**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e .
  pip install -r requirements-dev.txt
  pip install requests-mock>=1.12 freezegun>=1.5 'pytest-cov>=7.1' 'coverage>=7.13'
  ```
- **VALIDATE**: `pytest --version && coverage --version` succeeds.

#### Task 2: UPDATE `requirements-dev.txt`

- **ACTION**: Add the 4 new pinned dev deps.
- **IMPLEMENT**:
  ```
  requests-mock>=1.12
  freezegun>=1.5
  ```
  And bump `pytest-cov>=7.1`, add `coverage>=7.13`.
- **VALIDATE**: `pip install -r requirements-dev.txt` succeeds.

#### Task 3: UPDATE `pyproject.toml` — add pytest + coverage config

- **ACTION**: Append `[tool.pytest.ini_options]` and `[tool.coverage.*]` sections; bump `version = "1.0.5"` is already correct.
- **IMPLEMENT**:
  ```toml
  [tool.pytest.ini_options]
  addopts = [
      "--cov=pymercury",
      "--cov-branch",
      "--cov-report=term-missing",
      "--strict-markers",
  ]
  testpaths = ["tests"]

  [tool.coverage.run]
  branch = true
  omit = [
      "pymercury/api/client_backup.py",
      "*/tests/*",
  ]

  [tool.coverage.report]
  precision = 2
  exclude_also = [
      "if TYPE_CHECKING:",
      "if __name__ == .__main__.:",
      "raise NotImplementedError",
      "@(abc\\.)?abstractmethod",
  ]
  ```
- **GOTCHA**: Use `exclude_also`, NOT `exclude_lines` — `exclude_lines` overwrites built-in defaults including `pragma: no cover`. ([Coverage.py docs](https://coverage.readthedocs.io/en/latest/excluding.html))
- **GOTCHA**: Do NOT add `--cov-fail-under=100` yet — we add it in Task 28 after coverage actually reaches 100%.
- **VALIDATE**: `pytest -q` runs and prints coverage section.

### Phase B — Bug Fixes (Tasks 4-18)

Each fix has the failing test added FIRST (red), then the source change (green), then re-run.

#### Task 4: CRITICAL-5 — Fix `__version__`

- **ACTION**: Update `pymercury/__init__.py:97` from `"1.0.0"` to `"1.0.5"`.
- **VALIDATE**:
  ```python
  python3 -c "import pymercury; assert pymercury.__version__ == '1.0.5'"
  ```
- **TEST TO ADD** (`tests/test_imports.py`):
  ```python
  def test_version_matches_pyproject():
      from pymercury import __version__
      assert __version__ == "1.0.5"
  ```

#### Task 5: CRITICAL-1 — Fix `MercuryOAuthClient.login_or_refresh` `self.login()` AttributeError

- **ACTION**: `pymercury/oauth/client.py:486` change `return self.login(email, password)` → `return self.authenticate()` (note: `authenticate` takes no args; email/password are instance attrs from `__init__`).
- **TEST TO ADD** (`tests/test_oauth_client.py`):
  ```python
  def test_login_or_refresh_falls_back_to_authenticate(monkeypatch, requests_mock):
      client = MercuryOAuthClient("e@x.com", "pw")
      monkeypatch.setattr(client, "authenticate", lambda: "called-authenticate")
      result = client.login_or_refresh(existing_tokens=None)
      assert result == "called-authenticate"  # would AttributeError before fix
  ```
- **VALIDATE**: `pytest tests/test_oauth_client.py::test_login_or_refresh_falls_back_to_authenticate -v`

#### Task 6: CRITICAL-3 — Fix `_follow_redirects_for_code` to use the fresh session

- **ACTION**: `pymercury/oauth/client.py` — thread `session` parameter into `_follow_redirects_for_code(self, response, session)` and use `session.get(...)` instead of `self.session.get(...)` at line 385. Update the call site in `_mercury_combined_signin_post` to pass `fresh_session`.
- **TEST TO ADD** (`tests/test_oauth_client.py`): mock the redirect chain; assert that the auth code is extracted correctly when the second redirect requires the fresh session's cookies. (`requests_mock` register-history check: `requests_mock.request_history[i].headers['Cookie']` includes the fresh session's cookies.)
- **GOTCHA**: This is a behavioral fix — the OAuth flow may currently work because Mercury's redirects only require one hop. The test must construct a 2-hop redirect chain to actually demonstrate the fix.
- **VALIDATE**: New test passes; existing tests unchanged.

#### Task 7: CRITICAL-4 — Catch ValueError on int(env) in `MercuryConfig`

- **ACTION**: `pymercury/config.py:84-85`:
  ```python
  try:
      self.timeout = timeout if timeout is not None else int(os.getenv('MERCURY_TIMEOUT', '20'))
  except ValueError:
      raise MercuryConfigError("MERCURY_TIMEOUT must be a valid integer")

  try:
      self.max_redirects = max_redirects if max_redirects is not None else int(os.getenv('MERCURY_MAX_REDIRECTS', '5'))
  except ValueError:
      raise MercuryConfigError("MERCURY_MAX_REDIRECTS must be a valid integer")
  ```
- **TEST TO ADD** (`tests/test_configuration.py`):
  ```python
  def test_invalid_timeout_env_raises_config_error(monkeypatch):
      monkeypatch.setenv("MERCURY_TIMEOUT", "not-an-integer")
      with pytest.raises(MercuryConfigError, match="MERCURY_TIMEOUT"):
          MercuryConfig()
  ```
- **VALIDATE**: `pytest tests/test_configuration.py -v`

#### Task 8: CRITICAL-2 — Delete duplicate `service_usage` stub in endpoints

- **ACTION**: `pymercury/api/endpoints.py` — delete lines 43-45 (the 2-arg `service_usage` placeholder). Decide on lines 39 (`account_bills`) and 47 (`service_meter_readings`):
  - **Recommendation**: Delete both stubs unless maintainer wants them. If kept, add `# pragma: no cover` and a TODO.
- **TEST TO ADD** (`tests/test_endpoints.py`):
  ```python
  def test_only_one_service_usage_method():
      e = MercuryAPIEndpoints("https://api/v1")
      import inspect
      sig = inspect.signature(e.service_usage)
      assert len(sig.parameters) == 7  # the 7-arg version
  ```
- **VALIDATE**: `pytest tests/test_endpoints.py -v`

#### Task 9: HIGH-1 — Delete `pymercury/api/client_backup.py`

- **ACTION**: `git rm pymercury/api/client_backup.py`
- **VALIDATE**:
  ```bash
  ! grep -rn "client_backup" pymercury/ tests/  # must return nothing
  pytest -q  # all tests still pass
  ```

#### Task 10: HIGH-4 — Fix `OAuthTokens.__init__` to honor saved `expires_at`

- **ACTION**: `pymercury/oauth/client.py:33-42`:
  ```python
  saved_expires_at = token_data.get('expires_at')
  if saved_expires_at:
      try:
          self.expires_at = datetime.fromisoformat(saved_expires_at)
      except (TypeError, ValueError):
          self.expires_at = None
  elif self.expires_in:
      self.expires_at = datetime.now() + timedelta(seconds=int(self.expires_in))
  else:
      self.expires_at = None
  ```
- **TEST TO ADD** (`tests/test_oauth_client.py`):
  ```python
  def test_oauth_tokens_round_trip_preserves_expiry(fake_oauth_token_data):
      with freeze_time("2026-01-01 12:00:00"):
          original = OAuthTokens(fake_oauth_token_data)
          serialized = {
              **fake_oauth_token_data,
              "expires_at": original.expires_at.isoformat(),
          }
      with freeze_time("2026-01-01 12:30:00"):  # 30 min later
          reloaded = OAuthTokens(serialized)
          assert reloaded.expires_at == original.expires_at
          # Without fix, reloaded.expires_at would be 13:30:00 (recomputed)
  ```
- **VALIDATE**: `pytest tests/test_oauth_client.py::test_oauth_tokens_round_trip_preserves_expiry -v`

#### Task 11: HIGH-3 — Make `parse_mercury_json` try `json.loads` first

- **ACTION**: `pymercury/utils.py:36-43`:
  ```python
  def parse_mercury_json(text: str) -> Optional[Dict[Any, Any]]:
      try:
          return json.loads(text)
      except (json.JSONDecodeError, TypeError):
          pass
      for match in re.finditer(r'\{[^{}]*\}', text):
          try:
              return json.loads(match.group())
          except json.JSONDecodeError:
              continue
      return None
  ```
- **TEST TO ADD** (`tests/test_utilities.py`):
  ```python
  def test_parse_mercury_json_handles_nested_objects():
      result = parse_mercury_json('{"status":"200","data":{"foo":"bar"}}')
      assert result["status"] == "200"
      assert result["data"]["foo"] == "bar"

  def test_parse_mercury_json_falls_back_to_regex_on_garbage():
      result = parse_mercury_json('garbage prefix {"status":"200"} suffix')
      assert result == {"status": "200"}

  def test_parse_mercury_json_returns_none_when_no_json():
      assert parse_mercury_json("no json here") is None
  ```

#### Task 12: HIGH-5 + HIGH-10 — Remove unreachable `else: return None` and `'today' in locals()` antipattern

- **ACTION**: `pymercury/api/client.py`:
  - Remove the `if response.status_code == 200: ... else: return None` wrappers in every API method (lines ~146-153, 169-184, 203-223, etc.). After `_make_request` returns, just call `response.json()` directly. If a 404-as-`None` path is needed, catch `MercuryAPINotFoundError` explicitly.
  - Replace `'today' in locals()` (line 409) and `'yesterday' in locals()` (line 581, 639) with explicit sentinel:
    ```python
    end_dt_obj: Optional[datetime] = None
    if end_date is None:
        end_dt_obj = datetime.now(nz_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = quote(end_dt_obj.isoformat())
    if start_date is None:
        if end_dt_obj is None:
            end_dt_obj = datetime.fromisoformat(unquote(end_date))
        start_date = quote((end_dt_obj - timedelta(days=14)).isoformat())
    ```
- **TEST TO ADD** (`tests/test_api_client.py`): test `get_service_usage` with `end_date=None` (computes today) AND with explicit `end_date=quote("2026-01-15T00:00:00+13:00")` (parses provided date).
- **VALIDATE**: All existing tests still pass; new branch tests pass.

#### Task 13: HIGH-6 — Stop fabricating `previous_reading_value` / `consumption_kwh`

- **ACTION**: `pymercury/api/models/electricity.py:201-208` — set both to `None` and remove the arithmetic. Update docstring to say "value not provided by API endpoint".
- **TEST TO ADD** (`tests/test_models_electricity.py`):
  ```python
  def test_meter_reads_does_not_fabricate_previous_value():
      data = {"meterReads": [{"registers": [{"lastReading": "12500"}]}]}
      reads = ElectricityMeterReads(data)
      assert reads.previous_reading_value is None
      assert reads.consumption_kwh is None
  ```

#### Task 14: HIGH-7 — Stop fabricating GST / fixed-charge in `ElectricitySummary`

- **ACTION**: `pymercury/api/models/electricity.py:64-66` — set `daily_fixed_charge = None` and `gst_amount = None`. Remove arithmetic. Document.
- **TEST TO ADD** (`tests/test_models_electricity.py`): assert both fields are `None`.

#### Task 15: HIGH-8 — Tighten bare `except (json.JSONDecodeError, Exception)`

- **ACTION**: `pymercury/oauth/client.py:287` change to:
  ```python
  except (json.JSONDecodeError, KeyError, TypeError) as e:
  ```
  Also audit lines 355, 386, 445-447 for similar patterns. Replace bare `except Exception` with explicit tuples.
- **TEST TO ADD** (`tests/test_oauth_client.py`): construct an HTML response with no `var SETTINGS = {...}` to hit the JSON-decode path; assert log message but no swallowed `KeyboardInterrupt` (use `BaseException` raising in mock to verify it's not caught).

#### Task 16: HIGH-9 — Don't log raw responses containing potential credentials

- **ACTION**: `pymercury/oauth/client.py:319, 346` — change `_log(f"...: {auth_result}")` to `_log(f"...: status={auth_result.get('status')}")`. Never log raw response bodies.
- **TEST TO ADD** (`tests/test_oauth_client.py`): capture stdout via `capsys`; assert no token strings appear in verbose output even on failure paths.

#### Task 17: HIGH-2 — Add `close()` and context-manager support to client classes

- **ACTION**:
  ```python
  # pymercury/oauth/client.py and pymercury/api/client.py
  def close(self):
      self.session.close()
  def __enter__(self):
      return self
  def __exit__(self, exc_type, exc_val, exc_tb):
      self.close()
  ```
  Same for `MercuryClient` (delegating to `_oauth_client` and `_api_client`).
- **TEST TO ADD** (`tests/test_client_creation.py`): `with MercuryClient(...) as c: ...` then assert `c._oauth_client.session.adapters` are closed.

#### Task 18: HIGH-11 (DEFER decision) — Externalize hardcoded secrets

- **ACTION**: Discuss with maintainer whether to remove the hardcoded `client_id` / `api_subscription_key` defaults. If keep: add comment noting these are public B2C app credentials. If remove: env var required, `MercuryConfigError` if absent.
- **DEFAULT IN THIS PLAN**: keep defaults but mark with `# Public B2C app credential` comment, and add `MERCURY_CLIENT_ID` + `MERCURY_API_SUBSCRIPTION_KEY` to `.env.template`.
- **TEST TO ADD** (`tests/test_configuration.py`): `monkeypatch.delenv` + pass `client_id=""` explicit-empty → asserts `MercuryConfigError` is raised.

### Phase C — Coverage Track (Tasks 19-27)

#### Task 19: CREATE `tests/conftest.py`

- **ACTION**: Add `_fake_jwt`, `fake_oauth_token_data`, `restore_default_config` fixtures (see PATTERNS section above).
- **VALIDATE**: `pytest tests/ -q` still passes; new fixtures are discovered.

#### Task 20: UPDATE `tests/test_utilities.py` — utils.py to 100%

- **ACTION**: Add ~6 tests covering `extract_from_html` (success + ValueError), `parse_mercury_json` (3 paths from Task 11), `extract_auth_code_from_url` (with code, without code), `decode_jwt_payload` error branches (non-3-part token, invalid base64, payload that base64-decodes but isn't JSON).
- **VALIDATE**: `pytest --cov=pymercury.utils --cov-report=term-missing tests/test_utilities.py` shows 100%.

#### Task 21: UPDATE `tests/test_configuration.py` — config.py to 100%

- **ACTION**: Add ~12 tests covering all 8 `_validate` error branches (clear env vars, pass explicit empty/None), `timeout=0`, `max_redirects=-1`, `MERCURY_TIMEOUT=abc`, `MERCURY_MAX_REDIRECTS=abc`, `dotenv` import-fallback (mock `builtins.__import__` to raise `ImportError` for `dotenv`).
- **GOTCHA**: Use `importlib.reload` for the dotenv-fallback test; restore module via `restore_default_config` fixture.
- **VALIDATE**: `pytest --cov=pymercury.config --cov-report=term-missing tests/test_configuration.py` shows 100%.

#### Task 22: CREATE `tests/test_oauth_client.py` — oauth/client.py to 100%

- **ACTION**: Most invasive task. Add ~20 tests:
  - `OAuthTokens` field tests with full and minimal `token_data`
  - `OAuthTokens.is_expired`/`expires_soon`/`time_until_expiry`/`has_refresh_token` via `@freeze_time`
  - `OAuthTokens.name` with both/either/neither name parts
  - `MercuryOAuthClient.authenticate` happy path (mock all 6 HTTP calls with `requests_mock`)
  - Authentication failure (`status != "200"`) → `MercuryAuthenticationError`
  - CSRF/transId extraction failure (HTML without expected pattern) → `ValueError` propagates as `MercuryOAuthError`
  - `_extract_and_use_mercury_settings` failure (no `var SETTINGS`)
  - `_follow_redirects_for_code` — auth code in URL, in Location header, max-redirects exceeded
  - `_exchange_code_for_token` — happy path, non-200 (raise_for_status raises `requests.HTTPError`)
  - `refresh_tokens` — success, non-200 → None, exception → None
  - `login_or_refresh` — 3 branches: existing not expired, expires_soon → refresh, fall-through (Task 5 reproducer)
- **GOTCHA**: The 6-step PKCE flow needs all URLs registered with `requests_mock`. Use a helper fixture:
  ```python
  @pytest.fixture
  def mock_oauth_full_flow(requests_mock, fake_jwt):
      requests_mock.get("https://login.mercury.co.nz/.../authorize",
                        text='<html>...{"csrf":"c1","transId":"t1"}...</html>')
      requests_mock.post("https://login.mercury.co.nz/.../SelfAsserted",
                        text='{"status":"200"}')
      # ... etc
      requests_mock.post("https://login.mercury.co.nz/.../token",
                        json={"access_token": fake_jwt(), "refresh_token": "rt", "expires_in": 3600})
  ```
- **VALIDATE**: `pytest --cov=pymercury.oauth.client --cov-report=term-missing tests/test_oauth_client.py` shows 100%.

#### Task 23: UPDATE `tests/test_api_client.py` — api/client.py to 100%

- **ACTION**: ~25 tests:
  - Migrate existing `@patch('requests.Session.request')` tests to `requests_mock`
  - Fix the connection-error test: use `exc=requests.exceptions.ConnectionError("fail")` not bare `Exception`
  - Add 429 status → `MercuryAPIRateLimitError`
  - Add 500 status → `MercuryAPIError`
  - Add 403 status → `MercuryAPIError`
  - For each public method (`get_electricity_meter_info`, `get_bill_summary`, `get_usage_content`, `get_service_usage`, `get_electricity_summary`, `get_electricity_plans`, `get_electricity_meter_reads`, plus the gas / broadband variants): one happy path + one 404 not-found path
  - `get_services` — list response, dict-with-services response, dict-without-services response (all 3 isinstance branches)
  - `get_all_services` with 2 account_ids — exercises the loop
  - `get_service_usage` with `end_date=None` (computes today) and explicit `end_date` (parses provided)
  - `get_service_usage` with `start_date=None` and `start_date` provided
  - `get_electricity_plans` — happy path (mocks `get_services` to return service with `identifier`), no-ICP-found error, plans-fetch failure
  - `get_electricity_meter_reads` — dict response, list response, non-dict-non-list response
  - Use `@pytest.mark.parametrize` for status code tests:
    ```python
    @pytest.mark.parametrize("status,expected_exc", [
        (401, MercuryAPIUnauthorizedError),
        (404, MercuryAPINotFoundError),
        (429, MercuryAPIRateLimitError),
        (500, MercuryAPIError),
        (403, MercuryAPIError),
    ])
    def test_status_code_maps_to_exception(requests_mock, status, expected_exc):
        ...
    ```
- **VALIDATE**: `pytest --cov=pymercury.api.client --cov-report=term-missing` shows 100%.

#### Task 24: CREATE `tests/test_models_billing.py`

- **ACTION**: ~6 tests for `MeterInfo` (electricity_meter found in `meterservices`, not found, empty `meterservices`, `icp_number` fallback chain) and `BillSummary` (statement.details with electricity/gas/broadband line items, empty statement, missing optional fields).
- **VALIDATE**: `pytest --cov=pymercury.api.models.billing` shows 100%.

#### Task 25: CREATE `tests/test_models_electricity.py`

- **ACTION**: ~14 tests for `ElectricityUsageContent`, `ElectricitySummary` (weekly_usage with daily items vs empty, after-fix `None` fields from Task 14), `ElectricityPlans` (Daily Fixed Charge present + missing, Anytime rate present + missing, standard_plans/low_plans), `ElectricityMeterReads` (list-wrapped input, dict input, empty registers, non-numeric `lastReading` triggering `(ValueError, TypeError)` except, after-fix `None` fields from Task 13).
- **VALIDATE**: `pytest --cov=pymercury.api.models.electricity` shows 100%.

#### Task 26: CREATE `tests/test_client.py` — client.py to 100%

- **ACTION**: ~20 tests for `MercuryClient`:
  - `CompleteAccountData` instantiation + 5 properties
  - `MercuryClient.login` happy path (mock `oauth_client.authenticate`)
  - `MercuryClient.login` failure (no access_token) → `MercuryOAuthError`
  - `MercuryClient.smart_login` with existing tokens / without
  - `MercuryClient.refresh_if_needed` — 4 branches (no tokens / not expiring / refresh succeeds / refresh fails)
  - `MercuryClient._ensure_logged_in` — 5 branches (not logged in / expired+refresh OK / expired+refresh fails / expired no-refresh / expires_soon proactive refresh)
  - `MercuryClient.get_complete_account_data` — happy path, no customer_id, no accounts
  - `MercuryClient.is_logged_in`, `customer_id`, `account_ids`, `service_ids`, `access_token`, `email`, `name` properties
  - `MercuryClient.save_tokens` — with tokens, without tokens
  - `MercuryClient.load_tokens` — 5 branches incl. round-trip preserving `expires_at` (Task 10 reproducer)
  - `MercuryClient.login_with_saved_tokens` — 3 branches
  - `authenticate()` and `get_complete_data()` convenience functions
- **VALIDATE**: `pytest --cov=pymercury.client` shows 100%.

#### Task 27: UPDATE `tests/test_endpoints.py` — endpoints.py to 100%

- **ACTION**: After Task 8 deletes the dead stubs, all remaining methods should be testable. Add tests for any remaining uncovered URL-construction edge cases (e.g., `usage_content` with various `service_type` values, `service_usage` with unicode in dates, `bill_summary`).
- **VALIDATE**: `pytest --cov=pymercury.api.endpoints` shows 100%.

### Phase D — Gate (Task 28)

#### Task 28: Enable `--cov-fail-under=100` and verify

- **ACTION**: Edit `pyproject.toml` `[tool.pytest.ini_options]` `addopts` to add `"--cov-fail-under=100"`.
- **VALIDATE**:
  ```bash
  pytest -q  # must show "Required test coverage of 100% reached"
  ```
  Update `MANIFEST.in` to remove the reference to non-existent `test_mercury_library.py`.
- **NOTE**: If 100% is unattainable for legitimately unreachable code (e.g., the `else: return None` after `_make_request` raises on all errors), add `# pragma: no cover` with a comment explaining why. Document each pragma in the PR description.

---

## Testing Strategy

### Unit Tests to Write

| Test File | New / Updated | Test Cases | Validates |
|-----------|---------------|------------|-----------|
| `tests/conftest.py` | NEW | Fixtures: `fake_jwt`, `fake_oauth_token_data`, `restore_default_config` | Shared setup |
| `tests/test_utilities.py` | UPDATE | +6 cases | utils.py 100% |
| `tests/test_configuration.py` | UPDATE | +12 cases | config.py 100% incl. CRITICAL-4 |
| `tests/test_oauth_client.py` | NEW | ~20 cases | oauth/client.py 100% incl. CRITICAL-1, CRITICAL-3, HIGH-4 |
| `tests/test_api_client.py` | UPDATE | ~25 cases (parametrized status codes) | api/client.py 100% incl. fixed connection-error path |
| `tests/test_models_billing.py` | NEW | ~6 cases | billing.py 100% (was 7%) |
| `tests/test_models_electricity.py` | NEW | ~14 cases | electricity.py 100% incl. HIGH-6, HIGH-7 |
| `tests/test_client.py` | NEW | ~20 cases | client.py 100% incl. HIGH-4 round-trip |
| `tests/test_endpoints.py` | UPDATE | +4 cases | endpoints.py 100% after Task 8 |
| `tests/test_imports.py` | UPDATE | +1 case (version) | __version__ matches pyproject |
| `tests/test_client_creation.py` | UPDATE | +2 cases | Context-manager support (Task 17) |

**Total new tests: ~95.** Combined with existing 150 → ~245 tests.

### Edge Cases Checklist

- [ ] Empty/None inputs to every model `__init__`
- [ ] Missing optional keys in API JSON responses
- [ ] All HTTP error codes (401, 403, 404, 429, 500)
- [ ] `requests.exceptions.ConnectionError` vs `Timeout` vs generic `RequestException`
- [ ] JWT with no dots, with 2 dots, with non-base64 payload, with non-JSON-decodable payload
- [ ] Tokens expired vs not-yet-expired vs expiring-soon (`freezegun`)
- [ ] Token round-trip via `save_tokens` / `load_tokens` across time
- [ ] `MERCURY_TIMEOUT` set to non-integer
- [ ] `MERCURY_*` env vars cleared with explicit empty constructor args
- [ ] Multi-hop OAuth redirects requiring fresh-session cookies
- [ ] PKCE verifier/challenge reproducibility for given seed
- [ ] `get_service_usage` with explicit dates vs computed defaults
- [ ] `get_services` response shapes: dict-with-key, list, dict-without-key
- [ ] `ElectricityMeterReads` with list, dict, missing registers, non-numeric reading
- [ ] `BillSummary` with each line-item type (electricity/gas/broadband) and combinations

---

## Validation Commands

### Level 1: STATIC_ANALYSIS

```bash
source .venv/bin/activate
python -m black --check pymercury tests
python -m flake8 pymercury tests
python -m mypy pymercury  # may have pre-existing failures; do not regress
```

**EXPECT**: Exit 0 for `black` and `flake8`. `mypy` is informational; do not introduce new failures.

### Level 2: UNIT_TESTS

```bash
pytest tests/ -q
```

**EXPECT**: All ~245 tests pass.

### Level 3: COVERAGE

```bash
pytest --cov=pymercury --cov-branch --cov-report=term-missing
```

**EXPECT**: 100% line and branch coverage on every module except items pragma'd. Required-coverage gate enforced via `--cov-fail-under=100` in `pyproject.toml`.

### Level 4: BUILD

```bash
python -m build  # produces dist/mercury_co_nz_api-1.0.5-py3-none-any.whl
twine check dist/*
```

**EXPECT**: Build succeeds, twine reports no metadata issues.

### Level 5: SMOKE — `mercury_examples.py` (optional, requires real credentials)

Manual: skip in CI; run locally with real `.env` to confirm no regressions.

---

## Acceptance Criteria

- [ ] All 15 audit findings addressed (5 critical, 10 high) with a passing test that fails before the fix.
- [ ] `pymercury/api/client_backup.py` deleted.
- [ ] `pymercury.__version__ == "1.0.5"`.
- [ ] `pytest --cov=pymercury --cov-branch --cov-fail-under=100` exits 0.
- [ ] Every new/updated test asserts on a SPECIFIC exception type (no bare `pytest.raises(Exception)`).
- [ ] All HTTP-touching tests use `requests_mock` (no new `unittest.mock.patch('requests.Session.request')`).
- [ ] All time-sensitive tests use `freezegun` (no new `datetime` monkeypatches).
- [ ] No regressions: existing 150 tests still pass after migrations.
- [ ] `MANIFEST.in` no longer references missing `test_mercury_library.py`.
- [ ] `.env.template` documents all 10 env vars.
- [ ] `requirements-dev.txt` includes `requests-mock`, `freezegun`, pinned `pytest-cov>=7.1`, `coverage>=7.13`.

---

## Completion Checklist

- [ ] Phase A (Tasks 1-3) complete: venv set up, deps installed, pytest+coverage configured
- [ ] Phase B (Tasks 4-18) complete: all 15 bugs fixed, each with reproducer test
- [ ] Phase C (Tasks 19-27) complete: 9 test files created/updated, ~95 new tests
- [ ] Phase D (Task 28) complete: `--cov-fail-under=100` gate enabled and passing
- [ ] Level 1 (lint) clean
- [ ] Level 2 (unit tests) all pass
- [ ] Level 3 (coverage) at 100%
- [ ] Level 4 (build) succeeds
- [ ] All acceptance criteria met
- [ ] PR description lists every `# pragma: no cover` with justification

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OAuth fix (Task 6, CRITICAL-3) breaks the live login flow | MEDIUM | HIGH | Manually run `mercury_examples.py:example_1_simple_authentication` with real credentials before merging; keep the change behind a flag if uncertain |
| Removing fabricated `consumption_kwh = 100` (Task 13) breaks downstream consumers depending on the fake value | MEDIUM | MEDIUM | Document in CHANGELOG; major version bump may be warranted (1.0.5 → 1.1.0); flag in PR for maintainer decision |
| Migrating `unittest.mock` tests to `requests-mock` (Task 23) introduces test-rewrite bugs | MEDIUM | LOW | Migrate one test at a time; confirm green between each; keep old tests as `_legacy.py` until parity confirmed, then delete |
| `freezegun` incompatibility with Python 3.13 (target env) | LOW | MEDIUM | Pin `freezegun>=1.5` (handles py3.12+); fall back to `time-machine` if blocked |
| `--cov-fail-under=100` blocks merges due to legitimately-unreachable code | MEDIUM | LOW | Use `# pragma: no cover` sparingly with comments; document each in PR |
| Module-import-time `default_config = MercuryConfig()` makes config tests order-dependent | MEDIUM | LOW | `restore_default_config` autouse fixture in `conftest.py`; never call `importlib.reload` without it |
| Hardcoded secrets removal (HIGH-11) breaks public users who relied on defaults | HIGH | HIGH | Defer this fix; this plan only documents and adds env-var support, does NOT remove defaults; future major version |
| `int(os.getenv("MERCURY_TIMEOUT"))` fix changes import-time crash → MercuryConfigError but still crashes import | LOW | LOW | Document in CHANGELOG; this is the correct exception type |

---

## Notes

- **Why `requests-mock` over `responses`**: native pytest fixture (`requests_mock`), `exc=` parameter cleanly tests `requests.exceptions.RequestException` paths, sequential-response lists map to multi-step OAuth flows. See [requests-mock pytest fixture docs](https://requests-mock.readthedocs.io/en/latest/pytest.html).
- **Why `freezegun` over `monkeypatch.setattr`**: `from datetime import datetime` caches the class reference; patching after-the-fact misses it. `freezegun` patches at the C-level. See [freezegun GitHub](https://github.com/spulec/freezegun).
- **Why `exclude_also` not `exclude_lines`**: `exclude_lines` REPLACES coverage.py's built-in defaults — `# pragma: no cover` stops working. `exclude_also` APPENDS. Coverage.py 7.6+. See [Coverage.py — Excluding Code](https://coverage.readthedocs.io/en/latest/excluding.html).
- **Dead `else: return None` branches**: After Task 12 removes them, no `# pragma: no cover` is needed. If any remain, document each.
- **`extension_customerId` JWT claim**: The Mercury B2C tenant uses `extension_customerId` as the primary customerId claim. Fake JWTs in `conftest.py` must include it, or `OAuthTokens.customer_id` returns `None` and downstream tests break.
- **Order of env-var-clearing tests** (`test_configuration.py`): all use `monkeypatch.delenv(..., raising=False)`. monkeypatch auto-restores. Do not use raw `os.environ.pop`.
- **`mercury_examples.py` not run in CI**: requires real credentials. Documented as smoke-test for maintainer.
- **`_follow_redirects_for_code` (CRITICAL-3)**: The current code may work in practice because Mercury's redirect chain is single-hop. Task 6's test must construct a 2-hop chain to actually demonstrate the fix. If single-hop is the only real-world case, the fix is still correct (defensive) but is not currently producing observable failures.
- **`account_bills` and `service_meter_readings` endpoint stubs**: Not used internally and never reachable from public methods. Recommend deletion. If maintainer wants to keep them as planned future endpoints, add `# pragma: no cover` and a TODO.
- **Branch coverage for `if 'today' in locals():`**: After Task 12 replaces this with explicit sentinels, branch coverage is straightforward.
- **`python-dotenv` dependency placement**: it is in `requirements.txt` (runtime) but only listed under `[project.optional-dependencies].dev` in `pyproject.toml`. Inconsistency. Decide and align — recommend keeping it as optional and not requiring it (the `try/except ImportError` in `config.py:13-18` handles absence). Update `requirements.txt` accordingly OR add to `[project.dependencies]`.

**Confidence score for one-pass implementation**: 8/10.
- High because: all bugs identified with file:line, test patterns explicit, mocking library chosen and motivated, coverage gaps enumerated.
- Why not 10: (1) the OAuth flow's exact HTTP shape may differ slightly from the analyst's reading (will surface during Task 22); (2) Python 3.13 + freezegun edge cases unlikely but not pre-validated; (3) Task 18 (HIGH-11 secrets) is intentionally deferred and may require maintainer input; (4) some edge branches in `_make_request` may need a `# pragma: no cover` whose justification is judgment-call.
