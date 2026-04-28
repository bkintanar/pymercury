# Investigation: Gas usage shows wildly wrong values and silently drops estimated entries

**Issue**: free-form (no GitHub issue)
**Type**: BUG
**Investigated**: 2026-04-28

### Assessment

| Metric     | Value  | Reasoning |
| ---------- | ------ | --------- |
| Severity   | HIGH   | Two compounding correctness defects on the same endpoint: (a) for at least one date (2026-03-27), the SDK reports `158240 kWh` where Mercury's own dashboard reports `460 kWh` — a ~344× error that destroys all derived metrics (`total_usage`, `average`, `max`); (b) the SDK silently drops every entry Mercury labels `estimate`, so a real consumption month (2026-02-26 / 397 kWh in the user's account) doesn't appear at all. Both are silent — no error is raised, the numbers just lie. No clean workaround for downstream consumers. |
| Complexity | MEDIUM | The estimate-merge fix is one self-contained change in `_extract_usage_data` (`pymercury/api/models/base.py:66-90`) plus a `daily_usage` field addition in `ServiceUsage.__init__` (`base.py:170-179`). The 158240 fix is gated on a one-shot diagnostic capture (Mercury's actual gas response shape is not documented anywhere we control) and may be a 1-line field-name change OR a small per-point branching. ~3 files to change, ~50 LOC, 100% coverage gate must hold. |
| Confidence | MEDIUM | The estimate-filter root cause is **certain** (`base.py:85` — `if group.get('label') == 'actual': return ...`; documented at `test_models_usage.py:207-234` as the *intended* behavior). The 158240 root cause has three plausible candidates and cannot be disambiguated without one round-trip against the live API to capture `daily_gas.raw_data` for 2026-03-27 — the same diagnostic pattern the previous gas investigation used (`investigation-gas-empty-output.md`). |

---

## Problem Statement

`MercuryAPIClient.get_gas_usage*` returns numerically-incorrect data for a real piped-gas account in two distinct ways:

1. **Wrong magnitude** — for date `2026-03-27` the SDK reports `consumption = 158240` (kWh as the example labels them), where Mercury's own customer dashboard shows `460 kWh`. The 30 Jan entry on the same series is correct, ruling out a global units/scaling bug — only some entries are wrong.
2. **Missing entries** — Mercury's dashboard shows an `estimated` reading on `2026-02-26` of `397 kWh`. The SDK omits this entry entirely. Re-running the example or iterating `daily_gas.daily_usage` does not surface it.

Both defects originate inside `pymercury/api/models/base.py` and are observable through the `GasUsage` returned by every gas usage method (daily, hourly, monthly).

---

## Analysis

### Defect A — Estimated entries are silently dropped

**Root cause is certain.** `_extract_usage_data` short-circuits the moment it finds the `actual` group and discards every other group:

`pymercury/api/models/base.py:83-89`:

```python
# Shapes 1 & 2: groups with label + data
for group in usage_arrays:
    if isinstance(group, dict) and group.get('label') == 'actual':
        return group.get('data', []) or []
# Fallback: first group's data
if isinstance(first, dict):
    return first.get('data', []) or []
```

When Mercury returns:

```json
{
  "usage": [
    {"label": "actual",   "data": [{"date":"2026-01-30","consumption":...}, {"date":"2026-03-27","consumption":...}]},
    {"label": "estimate", "data": [{"date":"2026-02-26","consumption":397.0,...}]}
  ]
}
```

…the `estimate` group is never read. The intent ("prefer actual over estimate") is *documented* — `tests/test_models_usage.py:207-234` codifies it as `test_multiple_usage_arrays`:

```python
# Should prefer 'actual' data
assert len(usage.usage_data) == 1
assert usage.usage_data[0]['consumption'] == 10.0  # the actual point
assert usage.total_usage == 10.0
```

But this is wrong for gas. Gas meters are typically read every 2–3 months in NZ (per the comment at `mercury_examples.py:402-405`); estimated months fill the gap and are part of the user's actual billed consumption. Dropping them produces a series with holes that downstream consumers cannot detect.

**Why this didn't surface earlier:** every gas test in the suite uses a synthetic fixture with only an `actual` group, plus this one explicit "prefer actual" test. The behavior is locked in by tests. There's no test that asserts the *combined* shape Mercury actually returns for gas.

`ServiceUsage.usage_data` also has no `is_estimated` field, so even if we kept the estimate group, downstream consumers (and `mercury_examples.py:425-427`) couldn't visually distinguish estimated from actual. The fix needs both: keep both groups, and tag each point.

### Defect B — Single entry shows 158240 instead of 460

**Three hypotheses, in decreasing likelihood.** Cannot disambiguate without raw data.

#### Hypothesis B1 (~55%): Mercury embeds a cumulative meter reading on the latest data point

NZ utility APIs commonly return cumulative meter index alongside per-period delta. Compare electricity meter reads:

`pymercury/api/models/electricity.py:182-186`:

```python
self.latest_reading_value = primary_register.get('lastReading')   # cumulative kWh, e.g. 092822
self.latest_reading_date  = primary_register.get('lastReadDate')
self.latest_reading_type  = primary_register.get('lastReadType')  # "Actual" | "Estimated"
```

The user's electricity meter on the same date `2026-03-27` reports `092822 kWh` (cumulative; observed in `gas-shape.log:219-220`). It is plausible — even probable — that Mercury's gas usage endpoint returns each point as something like:

```json
{"date": "2026-03-27", "consumption": 460, "reading": 158240, "readType": "Actual"}
```

…where `consumption` is the per-period delta (correct for 30 Jan, would be correct for 27 Mar) and `reading` is the cumulative index. If that were the *only* shape, our parser (which reads `point.get('consumption', 0)`) would produce `460` and Defect B wouldn't exist.

The shape that **would** explain a `consumption == 158240` is one where Mercury, only on the most recent point, omits the `consumption` field entirely (because the reading isn't yet billed/rolled up) and our parser falls through to a different field — *or* a shape where `consumption` is overwritten with the cumulative index for the latest point. Variant: Mercury attaches a "summary" / "current-balance" record at the tail of the array with `consumption == cumulative-total`.

This hypothesis is testable in one shot: `print(json.dumps(daily_gas.raw_data, indent=2))` and look at the 2026-03-27 record.

#### Hypothesis B2 (~30%): Mercury returns the value in a different unit *only for some points*

If Mercury switches units (e.g., the per-period actuals are kWh but the latest unbilled reading is in scaled units), and the SDK doesn't honor a per-point `unit` field, the user sees a wildly different number for that one point. Less likely than B1 because the user's 30 Jan entry is correct AND the 397 kWh on 26 Feb (estimate) matches the dashboard — Mercury is internally consistent in kWh for actuals.

#### Hypothesis B3 (~15%): Two groups (`actual` + `usage` / `forecast` / `summary`) and `_extract_usage_data` lands on the wrong one for the 27 Mar entry

`_extract_usage_data` returns *one* group's data. If Mercury's gas response actually has:

```json
{
  "usage": [
    {"label": "actual",   "data": [...30 Jan correct...]},
    {"label": "estimate", "data": [...26 Feb missing...]},
    {"label": "summary",  "data": [{"date":"2026-03-27","consumption":158240,...}]}   // year-to-date totalizer
  ]
}
```

…and 30 Jan is *also* in the `summary` group with the right value, the picture changes. Lower likelihood because the SDK currently returns only the `actual` group, so a totalizer in another group wouldn't enter `usage_data`. But if the user's local environment has a tweaked parser, this is non-zero.

#### Why this affects March 27 specifically (across all hypotheses)

27 Mar is **the most recent meter read on the account** (matches the electricity meter's `lastReadDate: 2026-03-27` in `gas-shape.log:220`). All three hypotheses preferentially break the latest point — that's the entry whose semantics most often differ from older entries (current-period totalizer, current-meter-index, unbilled raw read).

### Why this didn't surface in the previous fix

The previous round (commits `b5111ca`, `a551ab3`) addressed:
- "no envelope key matches" → wrong shape returns 0 stats. Fixed.
- "diagnostic warning fires twice" → suppressed for subclasses. Fixed.

…but never inspected the *content* of the array Mercury returns for gas. The post-fix data points exist (`gas-shape.log:175 — Period: 2026-04-13 to 2026-04-27, but Monthly Data Points: 0`) — for the user's daily/hourly windows. The current report comes from a date range or interval that *did* return data: monthly with a window covering 30 Jan / 26 Feb / 27 Mar. None of that path was exercised.

### Affected Files

| File | Lines | Action | Description |
|------|-------|--------|-------------|
| `mercury_examples.py` | ~454 (after monthly_gas line) | UPDATE (temporary) | One-shot diagnostic dump of `monthly_gas.raw_data` to identify the actual envelope/field for the 27 Mar entry. Removed in Step 5. |
| `pymercury/api/models/base.py` | 66–90 | UPDATE | Replace "return only actual group" with merge-actual+estimate, sorted by date, each tagged with `is_estimated`. |
| `pymercury/api/models/base.py` | 168–179 | UPDATE | Add `is_estimated` (and possibly `read_type`) to the `daily_usage` dict produced for each point. |
| `pymercury/api/models/base.py` | TBD (Step 3) | UPDATE | Conditional fix for Defect B once raw shape is known. Likely candidates: (a) extract a per-point `consumption` ONLY from a known-good field name, (b) skip points where `consumption == cumulativeReading` if Mercury includes both, (c) skip a `summary`-labeled tail row. |
| `tests/test_models_usage.py` | 207–234 | UPDATE | Invert the existing `test_multiple_usage_arrays` expectation: `usage_data` should now contain BOTH points; `total_usage` = sum (or document the new contract). Add `is_estimated` assertions. |
| `tests/test_models_usage.py` | NEW class | UPDATE | Regression test using a sanitized real Mercury gas response captured in Step 1; assert 27 Mar value matches the dashboard, 26 Feb estimate is present and tagged. |
| `mercury_examples.py` | 425–427 | UPDATE | When printing daily gas breakdown, mark estimated entries: `f"{date}: {c:.2f} units{' (est)' if d['is_estimated'] else ''} (${cost:.2f})"`. |

### Integration Points

- `MercuryAPIClient.get_gas_usage` (`pymercury/api/client.py:444-475`) → `get_service_usage` (line 381) → `ServiceUsage(data)` (line 439) → returned as `GasUsage(service_usage.raw_data)` (line 473). The same `_extract_usage_data` is used for **electricity** (`api/client.py:547`); changes must keep electricity behavior compatible.
- `ElectricityUsage` (`pymercury/api/models/electricity.py:42`, `:70-74`) builds `weekly_total_usage` and statistics from the same `data.get('usage')` envelope and assumes only-actual semantics. **Decision point:** does merging estimates impact electricity? Electricity smart-meter data is typically *all actual* (no estimate group emitted), so the change is a no-op for electricity in practice — but verify against a captured electricity payload before flipping the test expectation.
- `mercury_examples.py:325-327` (electricity daily breakdown) and `:425-427` (gas daily breakdown) print the points; both need to honor the new `is_estimated` field if shown to users.
- `ServiceUsage.all_usage_arrays` (`base.py:131`) already preserves both groups — already-correct hook for downstream consumers who want the raw separation.

### Git History

- **Estimate-filter behavior introduced**: `31142b8` — *"feat: added gas and broadband services."* — the same commit that introduced gas+broadband also wrote the "prefer actual" branch. Latent ever since.
- **Test that locks the wrong behavior in**: introduced in `aef798e` (audit + 100% coverage push) at `tests/test_models_usage.py:207-234`. The test was added to lift coverage on the existing "prefer actual" branch — it codified the bug as the intended contract. The fix MUST update this test in lockstep, or the suite stays red.
- **Latest gas-related work**: `b5111ca` (envelope detection) and `a551ab3` (diagnostic gating). Neither inspected per-point content.
- **Implication**: long-standing latent bug for Defect A; Defect B is data-shape-dependent and may have been latent the same length of time, surfaced now because the previous fix finally lets gas data flow through the parser at all.

---

## Implementation Plan

### Step 1 — Capture Mercury's real gas response for 27 Mar / 26 Feb / 30 Jan

**File**: `mercury_examples.py`
**Action**: UPDATE (insert temporary diagnostic block; remove in Step 5)
**Where**: inside `example_5a_gas_usage_analysis`, immediately after the `monthly_gas = api_client.get_gas_usage_monthly(...)` call (around line 454).

**Insert**:

```python
# DIAGNOSTIC (temporary — remove after Step 3 lands; see investigation-gas-bad-values-and-missing-estimates.md)
import json, os
if monthly_gas and not os.environ.get("MERCURY_NO_DUMP"):
    print("\n=== RAW MONTHLY GAS RESPONSE (top-level keys) ===")
    print("Keys:", sorted(monthly_gas.raw_data.keys()))
    print("=== usage_arrays (full structure, first 4000 chars) ===")
    print(json.dumps(monthly_gas.raw_data.get("usage", "[no 'usage' key]"), indent=2, default=str)[:4000])
    # Also dump every alternate envelope our parser scans, in case Mercury changed shape
    for k in ("monthlyUsage", "hourlyUsage", "dailyUsage", "consumption", "usageData", "data"):
        if k in monthly_gas.raw_data:
            print(f"=== ALSO present at top level: {k} ===")
            print(json.dumps(monthly_gas.raw_data[k], indent=2, default=str)[:1000])
    print("=== END RAW DUMP ===\n")
```

**Why**: We need to see (a) the field names on the per-point dicts (does each point have `consumption`, `reading`, `readType`, `cost`, `unit`?), (b) whether estimates are in a separate `label='estimate'` group or interleaved within `label='actual'`, and (c) what the 27 Mar point looks like specifically. The previous investigation used the same hook (`investigation-gas-empty-output.md:158-167`); reusing the pattern is intentional.

**Run**:

```bash
python3 mercury_examples.py 2>&1 | tee gas-shape-v2.log
```

**Expected output to capture**:
- The list of label values (probably `actual` and `estimate`).
- For each data point in each group: the full dict, including any field that holds `158240` for 27 Mar.
- Compare to the 30 Jan and 26 Feb entries — find the field whose value differs in semantics.

---

### Step 2 — Merge `actual` + `estimate` groups and tag each point

This step is independent of Step 1 — confidence is already HIGH. It can land first.

#### Step 2a — Update `_extract_usage_data` to merge groups

**File**: `pymercury/api/models/base.py`
**Lines**: 66-90
**Action**: UPDATE

**Current code (base.py:83-89)** — short-circuits on `actual`:

```python
# Shapes 1 & 2: groups with label + data
for group in usage_arrays:
    if isinstance(group, dict) and group.get('label') == 'actual':
        return group.get('data', []) or []
# Fallback: first group's data
if isinstance(first, dict):
    return first.get('data', []) or []
return []
```

**Required change**: merge every group's data points into a single list, tagging each with its source label. Then sort by date so chronological order is preserved across labels.

```python
# Shapes 1 & 2: groups with label + data. Merge every group's points so
# 'estimate' entries (Mercury's gap-fillers between actual meter reads —
# common for piped gas) are visible to downstream consumers, not silently
# dropped. Each point is tagged with `is_estimated` so callers can
# distinguish; raw label is preserved as `read_type` for forward-compat.
groups_with_label = [
    g for g in usage_arrays
    if isinstance(g, dict) and isinstance(g.get('data'), list)
]
if groups_with_label:
    merged: List[Dict[str, Any]] = []
    for group in groups_with_label:
        label = group.get('label')
        for point in group.get('data', []) or []:
            if not isinstance(point, dict):
                continue
            tagged = dict(point)
            tagged.setdefault('is_estimated', label == 'estimate')
            tagged.setdefault('read_type', label)
            merged.append(tagged)
    # Sort by date so a merged actual+estimate series reads chronologically.
    merged.sort(key=lambda p: p.get('date') or '')
    return merged
return []
```

**Notes**:
- Drop the "fallback: first group's data" branch — the merge already covers single-group responses.
- `setdefault` is used so that if Mercury starts emitting `is_estimated` directly on a point, we don't overwrite it.
- Sort key uses `p.get('date') or ''` to keep ordering stable when dates are missing.
- The existing electricity behavior (one `actual` group, no `estimate`) yields the same list of points with `is_estimated == False` for each — fully backward-compatible for electricity callers that don't read the new field.

#### Step 2b — Surface `is_estimated` on the per-day dict

**File**: `pymercury/api/models/base.py`
**Lines**: 168-179
**Action**: UPDATE

**Current code (base.py:170-178)**:

```python
for usage_point in self.usage_data:
    daily_info = {
        'date': usage_point.get('date'),
        'consumption': usage_point.get('consumption'),
        'cost': usage_point.get('cost'),
        'free_power': usage_point.get('freePower'),
        'invoice_from': usage_point.get('invoiceFrom'),
        'invoice_to': usage_point.get('invoiceTo')
    }
    self.daily_usage.append(daily_info)
```

**Required change**:

```python
for usage_point in self.usage_data:
    daily_info = {
        'date': usage_point.get('date'),
        'consumption': usage_point.get('consumption'),
        'cost': usage_point.get('cost'),
        'free_power': usage_point.get('freePower'),
        'invoice_from': usage_point.get('invoiceFrom'),
        'invoice_to': usage_point.get('invoiceTo'),
        'is_estimated': bool(usage_point.get('is_estimated', False)),
        'read_type': usage_point.get('read_type'),
    }
    self.daily_usage.append(daily_info)
```

**Why**: `daily_usage` is the public dictionary downstream callers iterate (it's what `mercury_examples.py:425-427` walks). They need the flag to render estimated entries visibly.

#### Step 2c — Invert the existing test that locks in the wrong behavior

**File**: `tests/test_models_usage.py`
**Lines**: 207-234
**Action**: UPDATE

**Current `test_multiple_usage_arrays` (lines 207-234)** asserts only the actual point is present. Replace its assertions:

```python
def test_multiple_usage_arrays(self):
    """Test ServiceUsage with multiple usage arrays — both actual and estimate are kept."""
    data = {
        'serviceType': 'Gas',
        'usagePeriod': 'Daily',
        'usage': [
            {'label': 'estimate', 'data': [{'date': '2026-02-26', 'consumption': 397.0, 'cost': 49.5}]},
            {'label': 'actual',   'data': [{'date': '2026-01-30', 'consumption': 350.0, 'cost': 45.0},
                                           {'date': '2026-03-27', 'consumption': 460.0, 'cost': 60.0}]},
        ],
    }
    usage = ServiceUsage(data)

    # Both groups are now merged, sorted by date.
    assert len(usage.usage_data) == 3
    dates = [p['date'] for p in usage.usage_data]
    assert dates == ['2026-01-30', '2026-02-26', '2026-03-27']

    # Estimate is tagged.
    estimated = [p for p in usage.usage_data if p.get('is_estimated')]
    assert len(estimated) == 1
    assert estimated[0]['date'] == '2026-02-26'
    assert estimated[0]['consumption'] == 397.0

    # Stats include both actual and estimate consumption (Mercury bills both).
    assert usage.total_usage == 350.0 + 397.0 + 460.0
    assert usage.total_cost == 45.0 + 49.5 + 60.0
    assert usage.data_points == 3

    # daily_usage exposes the flag.
    assert any(d['is_estimated'] for d in usage.daily_usage)
```

Update `test_no_actual_data` (lines 236-255) similarly — when the only group is `estimate`, it's still kept (with `is_estimated=True`) instead of being treated as a fallback "actual".

#### Step 2d — Update the daily-breakdown rendering in the example

**File**: `mercury_examples.py`
**Lines**: 425-427
**Action**: UPDATE

```python
for i, day in enumerate(daily_gas.daily_usage[-3:], 1):
    date_str = day['date'][:10] if day['date'] else 'Unknown'
    marker = ' (estimated)' if day.get('is_estimated') else ''
    print(f"      {i}. {date_str}: {day['consumption']:.2f} units{marker} (${day['cost']:.2f})")
```

Apply the same pattern to the electricity daily breakdown at `mercury_examples.py:325-327` for consistency (electricity already gets `is_estimated=False` so behavior unchanged, but the marker hook is in place if Mercury ever flips a point).

---

### Step 3 — Fix the 158240-vs-460 anomaly (depends on Step 1 output)

**File**: `pymercury/api/models/base.py`
**Action**: UPDATE (specifics depend on which hypothesis Step 1 confirms)

Apply ONE of the branches below based on what `gas-shape-v2.log` reveals.

#### Branch B1 — Cumulative reading bleeds into `consumption` (most likely)

If the 27 Mar point looks like e.g.:

```json
{"date":"2026-03-27","reading":158240,"readType":"Actual","consumption":null,"cost":...}
```

…then `point.get('consumption', 0)` falls back to 0 *most* of the time, but somewhere in the chain (or in the actual JSON, `consumption: 158240`) the latest cumulative is leaking into the `consumption` field. The fix is to be explicit: prefer a known-delta field, and if the only field is a cumulative `reading`, compute the delta against the prior point.

```python
# In ServiceUsage.__init__ (base.py:136), replace the naive sum with:
def _delta_consumption(point: Dict[str, Any], prior: Optional[Dict[str, Any]]) -> float:
    # If Mercury gives us a per-period delta, use it.
    c = point.get('consumption')
    if isinstance(c, (int, float)):
        # Sanity-check: if `consumption` is implausibly large (>10× the median
        # of prior points), fall through to the meter-delta path.
        return float(c)
    # Fall back to (current_reading - prior_reading) for cumulative-only payloads.
    cur = point.get('reading') or point.get('meterReading')
    prv = (prior or {}).get('reading') or (prior or {}).get('meterReading')
    if isinstance(cur, (int, float)) and isinstance(prv, (int, float)):
        return float(cur) - float(prv)
    return 0.0
```

**Gotcha**: do not apply this branch unless Step 1 confirms a cumulative field exists. Speculating here introduces a different bug.

#### Branch B2 — Per-point `unit` field varies

If Step 1 shows a `unit` field on each point (e.g., `"unit":"kWh"` for 30 Jan, `"unit":"Wh"` or similar for 27 Mar), normalize to a single canonical unit before summing. Add a `_to_kwh(value, unit)` helper and apply at extraction time.

#### Branch B3 — Extra "summary" group polluting the merge

If Step 1 reveals a third group (e.g., `label: 'summary'` or `label: 'forecast'`) whose `data` contains a totalizer record, the Step 2 merge will accidentally include it. Constrain the merge to known data labels:

```python
KNOWN_DATA_LABELS = {'actual', 'estimate', 'estimated'}
groups_with_label = [
    g for g in usage_arrays
    if isinstance(g, dict)
    and isinstance(g.get('data'), list)
    and (g.get('label') is None or g.get('label') in KNOWN_DATA_LABELS)
]
```

…and either (a) emit a `logger.warning(...)` for any unrecognized label so we discover it, or (b) capture them on `self.unrecognized_groups` for diagnostic surfaces. Prefer (a) until we have a real-data driven need for (b).

---

### Step 4 — Add a regression test using the captured real response

**File**: `tests/test_models_usage.py`
**Action**: UPDATE (NEW class at end)

After Step 1, sanitize the captured response (replace customer/account/service IDs and any address fields with synthetic placeholders) and commit it as a fixture:

```python
class TestGasMonthlyRealShape:
    """Regression test pinned to the real Mercury gas response shape.

    Captured from a live monthly-interval response on 2026-MM-DD; PII-sanitized.
    Mirrors the symptoms in investigation-gas-bad-values-and-missing-estimates.md:
      - 30 Jan actual: ~350 kWh (reference value from Mercury dashboard)
      - 26 Feb estimate: 397 kWh (must be present, must be tagged is_estimated=True)
      - 27 Mar actual: 460 kWh (must NOT be the cumulative-reading value)
    """

    def test_real_monthly_response_shape(self):
        real_response = {
            # ... paste sanitized response from Step 1 ...
        }
        usage = GasUsage(real_response)

        # All three months present and chronological.
        assert [p['date'][:10] for p in usage.usage_data] == ['2026-01-30', '2026-02-26', '2026-03-27']

        # Estimate retained, tagged, sorted in.
        feb = next(p for p in usage.daily_usage if p['date'].startswith('2026-02'))
        assert feb['is_estimated'] is True
        assert feb['consumption'] == 397.0

        # 27 Mar matches dashboard, NOT the cumulative reading.
        mar = next(p for p in usage.daily_usage if p['date'].startswith('2026-03'))
        assert mar['consumption'] == 460.0
        assert mar['consumption'] != 158240
        assert mar['is_estimated'] is False

        # 30 Jan unchanged (the previously-correct entry).
        jan = next(p for p in usage.daily_usage if p['date'].startswith('2026-01'))
        assert jan['is_estimated'] is False
```

**Why**: the existing 333+ test suite uses synthetic fixtures; only a real-shape pin can prevent this exact regression from recurring. Treat the fixture as canonical — if Mercury changes shape later, this test will fail with a clear signal.

---

### Step 5 — Remove the diagnostic dump

After Step 1 captured the shape and Step 3 landed, delete the diagnostic block from `mercury_examples.py` introduced in Step 1. Re-run `python3 mercury_examples.py` end-to-end and confirm:

- Gas monthly section now shows 30 Jan, 26 Feb (with `(estimated)` marker), 27 Mar (with the correct ~460 value).
- Electricity output has not regressed (still shows non-zero stats; daily breakdown still renders).
- No `⚠️ ServiceUsage parsed 0 usage points` stderr line for gas.

---

## Patterns to Follow

**Re-use the diagnostic-dump pattern from the previous gas investigation:**

```python
# SOURCE: investigation-gas-empty-output.md:158-167 (already applied once successfully)
import json
if daily_gas:
    print("=== TOP-LEVEL KEYS:", list(daily_gas.raw_data.keys()))
    print(json.dumps(daily_gas.raw_data.get("usage", "[no 'usage' key]"), indent=2, default=str)[:4000])
```

**Mirror the existing test class structure for the regression test:**

```python
# SOURCE: tests/test_models_usage.py:207-234 — TestServiceUsageBasics::test_multiple_usage_arrays
# (The class to invert in Step 2c; pattern carries over to TestGasMonthlyRealShape in Step 4.)
class TestServiceUsageBasics:
    def test_multiple_usage_arrays(self):
        data = {'serviceType': 'Gas', 'usagePeriod': 'Daily', 'usage': [...]}
        usage = ServiceUsage(data)
        # …assertions…
```

**Mirror the per-point dict shape from the existing `daily_usage` builder:**

```python
# SOURCE: pymercury/api/models/base.py:170-178
daily_info = {
    'date':         usage_point.get('date'),
    'consumption':  usage_point.get('consumption'),
    'cost':         usage_point.get('cost'),
    # ... (Step 2b adds 'is_estimated' and 'read_type' here)
}
```

---

## Edge Cases & Risks

| Risk / Edge Case | Mitigation |
|---|---|
| Merging `estimate` into `usage_data` changes electricity statistics for accounts whose electricity payload happens to include an estimate group | Verify against a captured electricity payload (the user's account has electricity on the same dataset). If electricity emits estimates, Mercury already bills both — the merged stats are *more* correct, not less. Document the change in CHANGELOG and adjust any electricity test fixtures that hard-code an `estimate`-only path. |
| `_extract_usage_data` "shape 3" (flat list, no group wrapper) gets miscategorized as a group with the new merge | The `shape 3` early-return at `base.py:78-82` already takes the flat-list branch BEFORE the group merge — keep that guard. Add a unit test for "flat list with no `is_estimated` field" to confirm it stays untagged (`is_estimated == False`). |
| Real Mercury response contains PII (account_id, ICP, address, billing-period dates that hint at occupancy) | Sanitize the Step 4 fixture before committing — replace IDs with `'XXX'`-style placeholders; round costs; redact any address-shaped strings. Use `# DO NOT COMMIT REAL CREDENTIALS` comment on the diagnostic block in Step 1 (it's removed in Step 5 anyway). |
| Sorting points by date breaks if dates are absent or in mixed formats | Sort key uses `p.get('date') or ''` to keep ordering stable; points without dates collect at the front. For Mercury's actual gas data, every point has an ISO date — verified across the fixtures. |
| Unsorted electricity tests assume `usage_data` is in input order | The existing tests at `tests/test_models_usage.py:50-90` (and `:207-234`) only assert *contents*, not order, except for one — `test_grouped_with_actual_label` returns `[{"consumption": 10}, {"consumption": 20}]`. Since the new code preserves input order *within* a group (via `for group … for point …`) and groups have the same date, the sort is stable; the test still passes. Verify by running it. |
| Hypothesis B1's "fall back to delta from prior point" requires `usage_data` to be sorted by date first | Step 2's sort runs *before* Step 3's delta logic — order matters. Step 3's helper takes a `prior` arg that the caller threads through. |
| The "skip if `consumption` looks like a cumulative" heuristic in B1 false-positives on a legitimate 158-times spike | The heuristic is gated on `>10× median of prior points`. Realistic gas consumption variance is 3–5×; 10× is a safe threshold. Better still: only apply the heuristic when a `reading` field is present (i.e., when we have a meter delta to fall back to). Pure heuristic-only is rejected. |

---

## Validation

### Automated Checks

```bash
cd /var/www/personal/pymercury
/tmp/pymercury_venv/bin/pytest tests/ -q --no-cov
/tmp/pymercury_venv/bin/pytest tests/test_models_usage.py -v
/tmp/pymercury_venv/bin/pytest --cov=pymercury --cov-branch --cov-fail-under=100
```

**EXPECT**: 363+ tests pass (current baseline) plus the new TestGasMonthlyRealShape class (4+ tests). Coverage stays at 100% line + branch.

### Manual Verification

1. **Capture the shape** (Step 1): with real credentials in `.env`, run `python3 mercury_examples.py 2>&1 | tee gas-shape-v2.log` after inserting the diagnostic block.
2. **Inspect the dump**: open `gas-shape-v2.log`, find `=== RAW MONTHLY GAS RESPONSE ===`, verify (a) both `actual` and `estimate` groups appear, (b) the 27 Mar point's `consumption` field — is it `460` or `158240`?
3. **Apply Step 2** (estimate merge — no dependency on dump).
4. **Run example again, verify**: gas monthly section shows three rows for Jan/Feb/Mar; the Feb row prints `(estimated)`; the Mar row prints a value matching the user's Mercury dashboard.
5. **If Mar still shows 158240**: apply Step 3, branch B1/B2/B3 per the dump's content.
6. **Re-run example, confirm Mar = ~460**.
7. **Sanity-check electricity**: confirm electricity Daily Usage / Weekly Summary still match prior values; no new estimate markers appear (electricity smart-meter data is all actual).
8. **Diff `bill_summary.gas_amount`** with the new `total_usage` — they should approximately reconcile (cost-per-kWh × total_usage ≈ gas line item on the bill, within rounding).

---

## Scope Boundaries

**IN SCOPE:**

- One-shot diagnostic capture of the real gas monthly response (Step 1, removed in Step 5).
- Merging `actual` + `estimate` groups in `_extract_usage_data` (Step 2a).
- Adding `is_estimated` / `read_type` to `daily_usage` per-day dicts (Step 2b).
- Inverting `tests/test_models_usage.py::TestServiceUsageBasics::test_multiple_usage_arrays` (Step 2c).
- Marking estimated entries in `mercury_examples.py` daily breakdowns (Step 2d).
- Fixing the 158240-kWh anomaly per whichever B1/B2/B3 branch the dump reveals (Step 3).
- Pinning a sanitized real-response regression test (Step 4).

**OUT OF SCOPE (do not touch):**

- The "label-mismatch fallback" branch (`base.py:88-89`). It's already covered by the merged-groups path in Step 2a.
- Any change to the OAuth or session layers — pure model-layer fix.
- The `MercuryAPIClient.get_gas_usage_hourly` / `_monthly` date-default logic — already correct as of `b5111ca`.
- Renaming or moving the `is_estimated` flag to a separate `EstimatedReading` subclass. Keep the flag on the dict; subclassing per-point is gold-plating.
- Pydantic / `from_dict` model validation — already deferred to v2.0.0 in `v1.2.0-improvements.plan.md`.
- Adding a `forecast` group handler. Mercury may emit one but we have no live evidence; wait for Step 1 to confirm.
- Removing the `MERCURY_NO_USAGE_DIAG` env-var suppression (`base.py:98`). Keeps the previous fix's contract.

---

## Metadata

- **Investigated by**: Claude
- **Timestamp**: 2026-04-28
- **Artifact**: `.claude/PRPs/issues/investigation-gas-bad-values-and-missing-estimates.md`
- **Related prior investigation**: `.claude/PRPs/issues/investigation-gas-empty-output.md` (envelope-detection fix; closes the "all zeros" symptom but did not surface per-point content defects).
- **Suspected source files**:
  - Defect A (estimates dropped): `pymercury/api/models/base.py:83-89` — certain.
  - Defect B (158240 vs 460): `pymercury/api/models/base.py:136` (`consumptions = [point.get('consumption', 0) for point in self.usage_data]`) — likely; depends on Step 1 dump.
- **Confidence**: MEDIUM. Defect A is HIGH-confidence; Defect B requires one round-trip against the live API to confirm the per-point shape before the fix can be committed.
- **Next step**: `/prp-issue-fix investigation-gas-bad-values-and-missing-estimates` (run Step 1, then Steps 2a–2d, then 3 with the captured shape, then 4 + 5).
