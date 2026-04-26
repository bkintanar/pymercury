# Investigation: `mercury_examples.py` Gas section shows no usage data

**Issue**: free-form (no GitHub issue)
**Type**: BUG
**Investigated**: 2026-04-27

### Assessment

| Metric     | Value  | Reasoning |
| ---------- | ------ | --------- |
| Severity   | MEDIUM | The user's gas service IS detected and the API call returns 200; but every gas usage stat displays as `0.00` with empty daily breakdown — the example "runs" but communicates no actionable data. Workaround: switch to `include_all=True` (already tried per the diagnostic file) — doesn't help. |
| Complexity | LOW–MEDIUM | The likely fix is a single-file change to `pymercury/api/models/base.py` (and possibly an override in `pymercury/api/models/gas.py`) to handle a different response envelope. We can't size the change precisely until we see a real gas response body — needs a one-shot diagnostic capture before the fix. |
| Confidence | MEDIUM | Symptom is reproduced by the captured `mercury_examples.py.result` diagnostic file. Root cause is one of two shapes (response-envelope mismatch vs. genuinely-empty data); the diagnostic step in the implementation plan disambiguates them. |

---

## Problem Statement

Running `python3 mercury_examples.py` on an account that has a real piped-gas service produces no useful gas data: every numeric stat (`total_usage`, `total_cost`, `average_daily_usage`, `max_daily_usage`, `min_daily_usage`, `data_points`) prints as `0.00`, and the "Sample Daily Breakdown" shows zero entries. The Mercury API call succeeds (HTTP 200) — the SDK is silently parsing an empty/unknown shape into an all-zeros `GasUsage` object.

---

## Analysis

### Evidence Chain

**Symptom** — captured in the user's diagnostic `mercury_examples.py.result`:

```
DIAGNOSTIC: Services with include_all=True (find hidden gas service)
customer_id: 7334151
account_ids: ['834816299']

Default (include_all=False) — what our integration sees:
   • 'broadband' / 'Fibre' / 80101915345
   • 'gas' / 'Piped' / 80101901093
   • 'electricity' / 'Electricity' / 80101901092

  Trying get_gas_usage_monthly('7334151', '834816299', '80101901093'):
    → total_usage=0, total_cost=0, data_points=0
    → daily_usage entries: 0
```

This rules out service-detection bugs:
- Gas service IS visible at the account services endpoint with `serviceGroup='gas'`, `serviceType='Piped'`.
- `Service.is_gas` (`pymercury/api/models/account.py:51-53`) correctly matches.
- `ServiceIds.gas` (`pymercury/api/models/account.py:76-77`) correctly populates.

So the parse-failure must be downstream, in the usage-response handler.

↓ **WHY does `data_points = 0` after a 200 response?**

`ServiceUsage.__init__` at `pymercury/api/models/base.py:22-33`:

```python
# Extract usage data from Mercury.co.nz API format
usage_arrays = data.get('usage', [])
self.usage_data = []

# Mercury.co.nz returns usage in arrays with different labels (actual, estimate, etc.)
for usage_group in usage_arrays:
    if usage_group.get('label') == 'actual':
        self.usage_data = usage_group.get('data', [])
        break

# If no 'actual' data found, use the first available group
if not self.usage_data and usage_arrays:
    self.usage_data = usage_arrays[0].get('data', [])
```

`usage_data` only populates if Mercury returns the response with this exact envelope:

```json
{
  "usage": [
    {"label": "actual", "data": [{"date": ..., "consumption": ..., "cost": ...}, ...]}
  ]
}
```

If Mercury's gas response uses any other key (e.g. `monthlyUsage`, `consumption`, `data`, or wraps results under a `gas` key), `usage_arrays` becomes `[]` and `usage_data` stays `[]` — the `else` branch at `base.py:49-55` then sets every stat to `0`. The 200 response succeeds but produces an all-zeros object, exactly matching the user's symptom.

↓ **Confirming this is the root cause path** — `GasUsage` adds nothing on top of `ServiceUsage`:

`pymercury/api/models/gas.py:28-32`:

```python
class GasUsage(ServiceUsage):
    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)
```

So the entire parse responsibility is in `ServiceUsage.__init__`. There is no gas-specific parser anywhere in the SDK.

↓ **Why this didn't surface in tests** — every test that exercises gas usage uses a hand-built fixture that already conforms to the assumed shape:

`tests/test_api_client.py:222-234` (existing test):

```python
mock_response.json.return_value = {
    'serviceType': 'Gas',
    'usagePeriod': 'Daily',
    'usage': [
        {
            'label': 'actual',
            'data': [
                {'date': '2025-01-01', 'consumption': 324.0, 'cost': 91.08}
            ]
        }
    ]
}
```

Every gas test in the suite either uses this shape or mocks `get_service_usage` directly (skipping the parser). The 333-test suite is at 100% coverage but cannot detect a contract drift between the SDK's expected shape and Mercury's real shape.

### Root Cause Hypotheses (ranked)

1. **Envelope mismatch (most likely, ~70%)**: Mercury's gas usage endpoint returns the data under a different top-level key than `usage`. Possible alternatives observed in adjacent endpoints: `weeklySummary.usage`, `monthlySummary.usage`, `consumption`, `data`. The SDK silently parses the wrong envelope and produces zeros.

2. **Genuinely empty data (less likely, ~20%)**: Mercury returns the right envelope, but the user's gas hasn't been read in the queried window. Default monthly window is 1 year (`api/client.py:651`), which is unrealistic to be empty for active gas service. Default daily is 14 days; default hourly is 2 days — these COULD be empty for non-smart-meter gas (read every 2-3 months in NZ). But `_monthly` at 1 year should not be empty.

3. **`label` mismatch (low, ~10%)**: Gas response has `usage` array but no group has `label='actual'` AND `usage_arrays[0].get('data', [])` returns empty. The fallback at `base.py:32-33` should handle this; this is unlikely to be the sole cause.

We cannot disambiguate without inspecting `daily_gas.raw_data` from a real API call.

### Affected Files

| File | Lines | Action | Description |
|------|-------|--------|-------------|
| `mercury_examples.py` | 387–442 | UPDATE | Add a one-shot diagnostic dump of `daily_gas.raw_data` / `monthly_gas.raw_data` so we can see Mercury's actual response shape |
| `pymercury/api/models/base.py` | 22–55 | UPDATE | Make the parser handle the gas envelope shape we discover from the diagnostic; or fall back to scanning common alternative key names |
| `pymercury/api/models/gas.py` | 28–32 | (CONDITIONAL) UPDATE | Override `__init__` to pre-process gas-specific envelope before delegating to `super()`, IF the shape diverges enough that it's cleaner than touching the base class |
| `tests/test_models_usage.py` | NEW class | UPDATE | Add a test fixture that captures the REAL gas response shape and asserts non-zero stats |

### Integration Points

- `MercuryAPIClient.get_gas_usage` (`pymercury/api/client.py:445-470`) → `get_service_usage` → returns `ServiceUsage(data)` → cast to `GasUsage(service_usage.raw_data)`.
- The same `ServiceUsage.__init__` is called for **electricity** (which works correctly per the user's diagnostic). So whatever shape difference exists, electricity hits one branch and gas hits a different one.
- The `raw_data` attribute (set at `base.py:15`) preserves the original dict — diagnostic hook is one print statement away.

### Git History

- **Introduced**: `31142b8` — *"feat: added gas and broadband services."* — single commit added gas+broadband. No subsequent fixes to the gas usage parser. Implies the gas envelope assumption was made at the same time as electricity and never validated against a real gas response.
- **Implication**: Long-standing latent bug; not a regression. Likely never observable in dev because the original developer's account may have had no gas service or only `0.00`-billed gas.

---

## Implementation Plan

### Step 1 — Add a diagnostic dump to capture Mercury's gas response shape

**File**: `mercury_examples.py`
**Lines**: insert at line 391 (right after `daily_gas = api_client.get_gas_usage(...)`)
**Action**: UPDATE

**Insert this debug block** (temporary — remove or guard with an env var after the fix lands):

```python
# DIAGNOSTIC: dump raw response for shape inspection (see investigation-gas-empty-output.md)
import json
if daily_gas:
    print("\n=== RAW DAILY GAS RESPONSE (first 800 chars) ===")
    print(json.dumps(daily_gas.raw_data, indent=2, default=str)[:800])
    print("=== TOP-LEVEL KEYS:", list(daily_gas.raw_data.keys()))
    print("=== usage_arrays:", daily_gas.raw_data.get("usage", "[no 'usage' key]"))
    print()
```

**Why**: We need to see Mercury's actual JSON envelope before we can write a correct parser. `raw_data` is already preserved on every `ServiceUsage` instance (`base.py:15`).

**Run**: `python3 mercury_examples.py 2>&1 | tee gas-shape.log` and examine `gas-shape.log`.

---

### Step 2 — Identify the divergence

Compare the gas dump (from Step 1) against the electricity equivalent. Add the same `print(json.dumps(daily_electricity.raw_data, ...))` block in `example_5_electricity_usage_analysis` for an apples-to-apples diff.

Three possible outcomes:

| Outcome | Diagnosis | Step 3 action |
|---|---|---|
| Gas response has `usage_arrays = []` but other keys with data | **Envelope mismatch** | Update parser to handle the real key |
| Gas response has `usage` with `label='estimate'` only (no `actual`) | **Label mismatch** | Already handled by fallback at `base.py:32-33` — verify it's actually populating |
| Gas response has `usage` with empty `data` arrays | **Genuinely empty** | Document expected behavior; widen default time window for gas |

---

### Step 3 — Apply the parser fix (depends on Step 2 outcome)

Three branches based on what Step 2 reveals.

#### Branch A — Envelope mismatch

**File**: `pymercury/api/models/base.py`
**Lines**: 21–33
**Action**: UPDATE

Generalize the envelope detection. Replace the fixed `data.get('usage', [])` with a key-discovery scan:

```python
# Extract usage data from Mercury.co.nz API format. Mercury's gas response
# uses a different top-level envelope than electricity; scan for any of the
# known shapes.
USAGE_ENVELOPE_KEYS = ('usage', 'monthlyUsage', 'consumption', 'data')
usage_arrays = []
for envelope_key in USAGE_ENVELOPE_KEYS:
    candidate = data.get(envelope_key)
    if isinstance(candidate, list) and candidate:
        usage_arrays = candidate
        break
self.usage_data = []

# rest unchanged...
```

**Why**: Backward-compatible. Electricity (`usage` key) keeps working; gas (whatever its key is) starts working. Order matters — `usage` is checked first to preserve current behavior.

**Gotcha**: If Mercury's gas envelope uses a key not in this list, the diagnostic from Step 2 must inform the addition.

#### Branch B — Label mismatch (gas uses `'estimate'` not `'actual'`)

The fallback at `base.py:32-33` already handles this. If Step 2 reveals this is the case, no parser change is needed; the bug is somewhere else (probably the `data` arrays inside the groups are themselves empty — see Branch C).

#### Branch C — Genuinely empty

**File**: `pymercury/api/client.py`
**Lines**: 565-602 (`get_gas_usage_hourly`) and 682-721 (`get_gas_usage_monthly`)
**Action**: DOCUMENT

If Mercury legitimately has no gas usage data in the queried window (gas meters in NZ are often read every 2-3 months for non-smart meters), document this in the docstrings and update `mercury_examples.py` to print a clearer message:

```python
if daily_gas and daily_gas.data_points == 0:
    print("⚠️ No gas usage data in this date range — try a longer window or check your meter has been read.")
```

---

### Step 4 — Add a regression test using the REAL gas response shape

**File**: `tests/test_models_usage.py`
**Action**: UPDATE

Save the gas response captured in Step 1 as a JSON fixture (sanitize identifiers). Add a test that constructs `GasUsage(real_response)` and asserts non-zero stats:

```python
class TestGasUsageRealShape:
    """Regression test for the real Mercury gas response shape.

    Captured from a live response on 2026-MM-DD (PII-sanitized).
    """

    def test_real_gas_response_yields_non_empty_usage(self):
        # Replace this with the actual sanitized response from Step 1
        real_response = {
            "serviceType": "Gas",
            "usagePeriod": "Monthly",
            # ... whatever Mercury actually returns ...
        }
        usage = GasUsage(real_response)
        assert usage.data_points > 0
        assert usage.total_usage > 0
        assert len(usage.daily_usage) > 0
```

**Why**: Locks in the fix; prevents regression. The test suite currently uses synthetic fixtures that already conform to the (possibly-wrong) assumed shape, so this real-shape test is the only reliable check.

---

### Step 5 — Remove the diagnostic block from `mercury_examples.py`

After Step 3 fixes the parser, remove the debug `print(json.dumps(...))` block from Step 1 (it was temporary). Re-run `python3 mercury_examples.py` and confirm the gas section now prints non-zero stats.

---

## Patterns to Follow

**For the regression test, mirror this existing pattern from `tests/test_models_usage.py`:**

```python
# SOURCE: tests/test_models_usage.py — existing test class structure
class TestGasUsage:
    """Tests for GasUsage subclass of ServiceUsage."""

    def test_gas_usage_inherits_service_usage(self):
        data = {"serviceType": "Gas", "usagePeriod": "Daily", "usage": []}
        gu = GasUsage(data)
        assert isinstance(gu, ServiceUsage)
```

---

## Edge Cases & Risks

| Risk / Edge Case | Mitigation |
|---|---|
| Mercury's gas response shape varies per account / meter type (smart vs traditional) | Step 1 should run against the user's actual account so we see *their* shape, not a hypothetical one. Document any variance discovered. |
| Real gas response contains PII (account_id, ICP, address, customer name) | Sanitize the fixture before committing — replace IDs with synthetic placeholders. Use a `# DO NOT COMMIT REAL CREDENTIALS` comment on the diagnostic block. |
| Branch A (envelope scan) accidentally matches an unrelated `data` key on electricity responses | Order the keys with `usage` first; keep electricity's existing path unchanged. Run the full test suite after the change. |
| Adding `monthlyUsage` to envelope keys collides with `monthlySummary.usage` (different shape — wrapped one level deeper) | Step 2 must inspect the actual top-level keys. Don't speculate — fix only what Mercury actually returns. |
| The user runs `python3 mercury_examples.py` against a fresh account where gas hasn't been billed yet | Step 4 / Branch C handles this with a clearer "no data in window" message. |

---

## Validation

### Automated Checks

```bash
# After the parser fix lands:
cd /var/www/personal/pymercury
/tmp/pymercury_venv/bin/pytest tests/ -q --no-cov
/tmp/pymercury_venv/bin/pytest tests/test_models_usage.py::TestGasUsageRealShape -v
/tmp/pymercury_venv/bin/pytest --cov=pymercury --cov-branch --cov-fail-under=100
```

**EXPECT**: All 333+ tests pass (the new real-shape regression brings count to 334+); coverage stays at 100%.

### Manual Verification

1. **Capture the shape**: with real credentials in `.env`, run `python3 mercury_examples.py 2>&1 | tee gas-shape.log` after Step 1.
2. **Inspect the dump**: open `gas-shape.log`, find the `=== RAW DAILY GAS RESPONSE ===` block, identify Mercury's actual top-level envelope key for gas.
3. **Apply the fix**: per Step 3 Branch A/B/C.
4. **Re-run**: `python3 mercury_examples.py` — Gas section should now print non-zero `Total Usage`, `Total Cost`, etc., and the "Sample Daily Breakdown" should list the last 3 days of consumption.
5. **Sanity-check electricity**: confirm electricity output didn't regress (still shows non-zero stats).

---

## Scope Boundaries

**IN SCOPE:**
- Diagnostic capture of the real gas response shape (Step 1)
- Parser fix in `ServiceUsage.__init__` to handle the discovered shape (Step 3)
- Regression test using the real response (Step 4)
- Cleanup of the diagnostic block (Step 5)

**OUT OF SCOPE (do not touch):**
- Async support — already deferred to v2.0.0
- Pydantic-based model validation — would solve the "silent shape failure" problem entirely but is a much larger change; deferred to v2.0.0
- Removing hardcoded `client_id` / `api_subscription_key` defaults (HIGH-11) — separate concern
- Changing `ServiceUsage` inheritance (the question of whether `GasUsage` and `ElectricityUsage` add anything) — out of scope
- Pagination — not relevant here

---

## Metadata

- **Investigated by**: Claude
- **Timestamp**: 2026-04-27
- **Artifact**: `.claude/PRPs/issues/investigation-gas-empty-output.md`
- **Evidence file**: `mercury_examples.py.result` (captured user diagnostic showing zeros)
- **Suspected source file**: `pymercury/api/models/base.py:22-55`
- **Confidence**: MEDIUM — the parser-shape mismatch hypothesis fits the symptom precisely, but the actual fix shape can only be confirmed by inspecting a real Mercury gas response (Step 1).
