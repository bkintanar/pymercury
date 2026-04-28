# Investigation: Gas usage shows 164,220 kWh in HA energy dashboard despite pymercury 1.1.2 fixes

**Issue**: free-form (no GitHub issue)
**Type**: BUG (cross-repo: defect lives in `home-assistant-mercury-co-nz`; pymercury can ship an ergonomics improvement that prevents the class of bug)
**Investigated**: 2026-04-28

### Assessment

| Metric     | Value  | Reasoning |
| ---------- | ------ | --------- |
| Severity   | MEDIUM (HA-side); LOW (pymercury-side) | The user-visible symptom is incorrect numbers in their Home Assistant energy dashboard (164,220 kWh for 2026-03-27 vs. the real ~460 kWh) — that's high impact for THEIR use case, but the defect is in `home-assistant-mercury-co-nz/custom_components/mercury_co_nz/statistics.py:259-273`, not in pymercury. pymercury's role is enabling the class of bug by exposing a `daily_usage` shape (parallel `actual`/`estimate` pairs with one zero per pair) that's footgunny for downstream consumers. The first-time live-API capture in this investigation (see Evidence) finally documents what Mercury actually returns; previous investigations only had user-summary-level evidence. |
| Complexity | LOW (pymercury-side) | One additive property on `ServiceUsage`/`GasUsage` (`consumption_periods`) plus tests. ~30 LOC. The HA-side fix is also low — single-function rewrite in `_build_monthly_entries` to prefer the non-zero of each (estimate, actual) pair — but lives in a different repo. |
| Confidence | HIGH (root cause for the SHAPE issue); MEDIUM (root cause for the EXACT 164220 number) | Mercury's real gas response shape is captured in `/tmp/gas_probe.json` — definitively two parallel groups (`estimate` + `actual`), 10 entries each, with mutually-exclusive non-zero values. The `_build_monthly_entries` overwrite bug is unambiguous. The exact `460 × 357 = 164220` arithmetic match strongly suggests HA's statistics importer is failing to dedupe across polls, but I did not exhaustively trace HA's `async_add_external_statistics` call to confirm. |

---

## Problem Statement

The user's Home Assistant energy dashboard displays **164,220 kWh** for 2026-03-27 gas consumption. pymercury 1.1.2 (PR #5 + PR #6) returns the **correct** value for that date: 460 kWh actual, with `total_usage = 4842` over the year and no 158k/164k value anywhere in the response.

The 164,220 value originates inside `home-assistant-mercury-co-nz/custom_components/mercury_co_nz/statistics.py`, which consumes pymercury's `daily_usage` and writes HA `StatisticData` entries. Two compounding defects on the HA side:

1. **Estimated readings get overwritten by the zero-pair partner.** Mercury returns each billing period as TWO entries (one in `actual` group, one in `estimate` group, with one being 0 and the other being the real value). pymercury merges and sorts them; HA bucketizes them into a `dict[anchor] = (kwh, cost)` map keyed by `invoice_to`. When two entries share the same anchor, the second write wins. Because pymercury sorts stably with `estimate` first (the group order in Mercury's payload), the `actual=0` partner overwrites the `estimate=397` real value for estimated months.
2. **Stale statistics are never reconciled.** The `460 × 357 = 164,220` arithmetic identity is too clean to be coincidence — `_build_monthly_entries` is writing March 27's entry on every poll (or close to it) and the cumulative sum balloons because `cutoff_ts` filtering or `async_add_external_statistics` upsert isn't behaving as expected.

pymercury can prevent the **first** defect (and make the integration more correct end-to-end) by exposing a "collapsed" per-period view that hides the parallel-zero structure entirely.

---

## Analysis

### What Mercury Actually Returns (first-time live capture)

Probed against the user's account on 2026-04-28T22:10 NZ via `/tmp/probe_gas_shape.py`. Sanitized output at `/tmp/gas_probe.json`. Top-level shape:

```json
{
  "serviceType": "Gas",
  "usagePeriod": "Monthly",
  "startDate": "2025-04-28T22:10:09+12:00",
  "endDate":   "2026-04-28T22:10:09+12:00",
  "usage": [
    {"label": "estimate", "colour": "#eef0ee", "fill": "striped",
     "data": [{"date":"2025-07-01","invoiceFrom":"2025-06-14","invoiceTo":"2025-07-01","cost":0,"consumption":0,...}, ...10 entries]},
    {"label": "actual",   "colour": "#fff100", "fill": "solid",
     "data": [{"date":"2025-07-01","invoiceFrom":"2025-06-14","invoiceTo":"2025-07-01","cost":91.08,"consumption":324,...}, ...10 entries]}
  ],
  "annotations": [],
  "averageTemperature": null
}
```

**Critical insight**: the two groups are **parallel**, not disjoint. For each billing period (10 of them in this account's year of history), Mercury emits **one entry in each group**. One entry has the real consumption + cost; the other has zeros. There is no third "summary" or "forecast" group on this account — Hypothesis B3 from the previous investigation was wrong, but the `KNOWN_DATA_LABELS` allowlist is still correct hardening.

Walking the parallel pairs (consumption, with `e=estimate, a=actual`):

| Period (`invoice_to`) | estimate | actual | Real value | Tag |
|----|---:|---:|---:|---|
| 2025-07-01 | 0 | **324** | 324 | actual |
| 2025-07-30 | **517** | 0 | 517 | estimate |
| 2025-08-29 | 0 | **539** | 539 | actual |
| 2025-09-30 | **571** | 0 | 571 | estimate |
| 2025-10-30 | 0 | **635** | 635 | actual |
| 2025-11-27 | 0 | **463** | 463 | actual |
| 2025-12-27 | **493** | 0 | 493 | estimate |
| 2026-01-30 | 0 | **443** | 443 | actual |
| 2026-02-26 | **397** | 0 | 397 | estimate |
| 2026-03-27 | 0 | **460** | 460 | actual |

Sum of real values = **4842 kWh** = pymercury's `total_usage`. ✓

After PR #5 + PR #6 (current 1.1.2), pymercury's `daily_usage` exposes all 20 entries (10 estimate + 10 actual), sorted by date, each tagged with `is_estimated` and `read_type`. The pair structure is preserved — consumers must filter or pick the non-zero of each pair.

### The HA Bug (cross-repo)

`home-assistant-mercury-co-nz/custom_components/mercury_co_nz/statistics.py:255-298` — `_build_monthly_entries` builds a `dict[anchor] = (kwh, cost)` from the 20-entry list:

```python
buckets: dict[datetime, tuple[float, float]] = {}
for record in monthly_records or []:
    invoice_to_raw = record.get("invoice_to") or record.get("date")
    if not isinstance(invoice_to_raw, str):
        skipped += 1
        continue
    anchor = MercuryStatisticsImporter._parse_invoice_end_utc(invoice_to_raw)
    ...
    consumption = record.get("consumption")
    cost = record.get("cost")
    if consumption is None or cost is None:
        skipped += 1
        continue
    buckets[anchor] = (float(consumption), float(cost))   # ← LAST WRITE WINS
```

Two records share each `invoice_to` anchor (the `estimate` and `actual` pair). The dict overwrite means the **last** record for each anchor wins. Because pymercury sorts stably and `estimate` is the first group in Mercury's payload, `estimate` is iterated first, then `actual` overwrites:

- 2026-03-27: estimate(0) written → actual(460) overwrites → bucket=460 ✓
- 2026-02-26: estimate(397) written → actual(0) overwrites → bucket=0 ✗ (lost the real value)
- 2025-07-30: estimate(517) written → actual(0) overwrites → bucket=0 ✗
- 2025-09-30: estimate(571) written → actual(0) overwrites → bucket=0 ✗
- 2025-12-27: estimate(493) written → actual(0) overwrites → bucket=0 ✗

Sum of buckets after this overwrite: 324 + 0 + 539 + 0 + 635 + 463 + 0 + 443 + 0 + 460 = **2864 kWh** (vs. the real 4842). The integration is undercounting by 1978 kWh.

The 164,220 figure is harder to fully explain without instrumenting HA — but `460 × 357 ≈ 164,220` is a clean enough identity that the most likely failure is the importer NOT deduping cleanly across polls (the `cutoff_ts` filter at line 280 should skip already-imported anchors, but if `last_start_ts` returns a stale value or `async_add_external_statistics` isn't upserting by `(statistic_id, start)` for some reason, March 27's entry would be re-emitted on each poll, causing the cumulative `sum` to keep growing).

### What pymercury Can Do

**The HA bug is real, but pymercury makes it easy to write.** Today, downstream consumers have to:

1. Iterate `daily_usage` and group by `invoice_to`.
2. For each pair, prefer the non-zero entry (with `is_estimated` metadata).
3. Build their own collapsed view.

This is exactly what `_build_monthly_entries` *should* be doing but isn't. Other downstream consumers will hit the same trap. **Adding a `consumption_periods` property to `ServiceUsage`** that pre-collapses the pairs is a one-shot ergonomic fix that prevents the class of bug:

```python
class ServiceUsage:
    @property
    def consumption_periods(self) -> List[Dict[str, Any]]:
        """One entry per billing period (collapsed estimate+actual pair).

        For each unique (invoice_from, invoice_to) tuple, returns the entry
        with the larger non-zero consumption value (preferring 'actual' over
        'estimate' if both are non-zero). Each entry is tagged with
        `is_estimated` so downstream consumers (HA energy dashboards,
        reporting tools) can render the source without needing to walk
        the parallel pair structure themselves.
        """
        ...
```

This is purely additive — no behavior change for callers using `daily_usage` or `total_usage`. The HA integration can switch to `consumption_periods` and drop its own bucketize-and-overwrite logic.

### Affected Files

| File | Lines | Action | Description |
|------|-------|--------|-------------|
| `pymercury/api/models/base.py` | After line 191 (end of `ServiceUsage.__init__`) | UPDATE | Add `consumption_periods` property — collapses `daily_usage` pairs to one entry per `(invoice_from, invoice_to)`, preferring the non-zero entry (preferring `actual` if both non-zero). Computes lazily; reads `self.daily_usage`. |
| `tests/test_models_usage.py` | NEW class `TestConsumptionPeriods` | UPDATE | Tests using the captured real-shape fixture from `/tmp/gas_probe.json` (sanitized): 20 daily_usage entries → 10 collapsed periods; estimate-only periods preserve `is_estimated=True`; actual-only periods get `is_estimated=False`; sum of `consumption_periods` consumptions equals `total_usage`. |
| `mercury_examples.py` | example_5a monthly section (lines 454-475) | UPDATE | Demo the new `consumption_periods` property alongside the existing breakdown — shows the collapsed view (10 rows, no zero-pair noise). |
| `home-assistant-mercury-co-nz` | `custom_components/mercury_co_nz/statistics.py:255-298` | DOC ONLY (different repo) | Documented as the actual root cause; out of scope for this artifact but called out for the user to fix in that repo. The clean fix once pymercury 1.1.3 ships: replace the `for record in monthly_records` loop with `for record in gas_monthly.consumption_periods`, eliminating the bucket dict entirely. |

### Integration Points

- `mercury_examples.py:454-475` (monthly gas section) — already renders `daily_usage[-6:]`; the new property is shown alongside.
- `home-assistant-mercury-co-nz/custom_components/mercury_co_nz/mercury_api.py:982` — currently `monthly_history = list(getattr(gas_monthly, "daily_usage", []) or [])`. After the fix, it should be `getattr(gas_monthly, "consumption_periods", [])`.
- `home-assistant-mercury-co-nz/custom_components/mercury_co_nz/statistics.py:259-273` — current bucketize-then-overwrite loop is the actual bug site. Once `consumption_periods` is consumed, the bucketize step disappears and `_build_monthly_entries` becomes a straight chronological walk.

### Why This Wasn't Caught Before

- The previous investigation (`investigation-gas-bad-values-and-missing-estimates.md`, closed via PR #5/#6) was focused on the per-record values inside `daily_usage`, not the overall structure (parallel pairs).
- Synthetic test fixtures used in `test_models_usage.py` model the parallel structure as written but don't include the `invoice_from`/`invoice_to` fields, so downstream-consumer ergonomics issues weren't surfaced.
- The user's first report ("27 March = 158240") was assumed to be a `summary`/`forecast` group totalizer (Hypothesis B3) — the live capture now disproves that hypothesis. Mercury's response has only `estimate` + `actual`, no third totalizer group on this account.
- The 158240→164220 drift over ~24h was the genuine signal that the value is downstream-accumulated, not a single Mercury field. Should have prompted asking "where exactly are you seeing this?" sooner — the user clarified mid-investigation: "I'm getting this in the HA energy dashboard itself."

### Git History

- pymercury's parallel-pair handling: introduced in PR #5 (`4786d19`) — `_extract_usage_data` merge + `is_estimated`/`read_type` tags. Hardened in PR #6 (`8cf6f3f`) with `KNOWN_DATA_LABELS` allowlist. Both correct for what they did; this artifact is a follow-up enhancement.
- `home-assistant-mercury-co-nz` repo activity not inspected here; the fix lives there.

---

## Implementation Plan

### Step 1 — Add `consumption_periods` property to `ServiceUsage`

**File**: `pymercury/api/models/base.py`
**Lines**: insert immediately after `self.annotations = data.get('annotations', [])` (currently line 191, end of `__init__`)
**Action**: UPDATE

Compute lazily inside the existing class. Implementation:

```python
@property
def consumption_periods(self) -> List[Dict[str, Any]]:
    """One entry per billing period — collapses the estimate+actual pair.

    Mercury returns gas (and possibly other) usage as two parallel groups:
    `estimate` and `actual`. For each billing period, both groups emit a
    record at the same `(invoice_from, invoice_to)` window, but only ONE
    has a non-zero consumption — the other is a placeholder zero. Walking
    `daily_usage` directly gives consumers double the rows and forces them
    to handle the pair structure themselves; bucketize-by-anchor with a
    naive `dict[anchor] = ...` assignment causes the second-written entry
    to clobber the first, losing the real value for either estimated or
    actual months depending on group order.

    This property collapses each pair to a single entry:

    1. Group `daily_usage` entries by `(invoice_from, invoice_to)` (or
       `date` if invoice fields are absent — flat-list-shape compat).
    2. For each group, choose the entry with the largest non-zero
       `consumption`. Ties broken by preferring `actual` over `estimate`
       (so a fully-zero pair still picks the actual, with consumption=0).
    3. Preserve all original fields plus the `is_estimated` / `read_type`
       tags from PR #5.

    Returned in chronological order (sorted by `invoice_to` then `date`).
    """
    from collections import defaultdict

    if not self.daily_usage:
        return []

    def _key(d: Dict[str, Any]) -> tuple:
        # Group by invoice window if present; fall back to date.
        return (
            d.get('invoice_from') or '',
            d.get('invoice_to') or d.get('date') or '',
        )

    grouped: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for entry in self.daily_usage:
        grouped[_key(entry)].append(entry)

    collapsed: List[Dict[str, Any]] = []
    for key, entries in grouped.items():
        if len(entries) == 1:
            collapsed.append(entries[0])
            continue
        # Multiple entries share this period — pick the best.
        # Sort: largest non-zero consumption first; ties go to 'actual'.
        def _rank(e: Dict[str, Any]) -> tuple:
            c = e.get('consumption') or 0
            # (-consumption: bigger first; estimated last on ties so actual wins)
            return (-float(c), 1 if e.get('is_estimated') else 0)
        entries_sorted = sorted(entries, key=_rank)
        collapsed.append(entries_sorted[0])

    # Final chronological order on (invoice_to, date).
    collapsed.sort(key=lambda d: (d.get('invoice_to') or d.get('date') or ''))
    return collapsed
```

**Why a property, not a precomputed list in `__init__`**: avoids a second pass in the hot init path and keeps the pre-PR-5 attribute set unchanged for any test that does `dir(usage)` or pickle round-trips.

**Why prefer the largest non-zero, not the actual group**: future-proof. If Mercury ever returns BOTH estimate and actual with non-zero values for the same period (e.g., correction issued mid-month), picking the larger is the more conservative bill-reconciliation choice. Tie-breaker `actual > estimate` matches the convention of "actual wins when both are equally valid".

---

### Step 2 — Add tests using the captured real shape

**File**: `tests/test_models_usage.py`
**Action**: UPDATE — add `TestConsumptionPeriods` class

```python
class TestConsumptionPeriods:
    """Tests for ServiceUsage.consumption_periods — the collapsed-pair view.

    Captured from the user's real Mercury gas response on 2026-04-28
    (PII-sanitized) at /tmp/gas_probe.json. Mercury returns each billing
    period as two parallel entries: one in 'estimate', one in 'actual',
    with one zero and one non-zero per pair. consumption_periods collapses
    the pair to one entry, preferring the non-zero (preferring actual on
    ties). Downstream consumers (HA statistics, reporting) can iterate
    consumption_periods directly without bucketize-and-overwrite logic.
    """

    @pytest.fixture
    def real_gas_monthly_response(self):
        # 10 billing periods, parallel estimate+actual groups.
        # Values pinned from /tmp/gas_probe.json (2026-04-28 capture).
        return {
            'serviceType': 'Gas',
            'usagePeriod': 'Monthly',
            'usage': [
                {'label': 'estimate', 'data': [
                    {'date': '2025-07-01', 'invoiceFrom': '2025-06-14', 'invoiceTo': '2025-07-01', 'consumption': 0,   'cost': 0},
                    {'date': '2025-07-30', 'invoiceFrom': '2025-07-02', 'invoiceTo': '2025-07-30', 'consumption': 517, 'cost': 145.86},
                    {'date': '2025-08-29', 'invoiceFrom': '2025-07-31', 'invoiceTo': '2025-08-29', 'consumption': 0,   'cost': 0},
                    {'date': '2025-09-30', 'invoiceFrom': '2025-08-30', 'invoiceTo': '2025-09-30', 'consumption': 571, 'cost': 183.68},
                    {'date': '2025-10-30', 'invoiceFrom': '2025-10-01', 'invoiceTo': '2025-10-30', 'consumption': 0,   'cost': 0},
                    {'date': '2025-11-27', 'invoiceFrom': '2025-10-31', 'invoiceTo': '2025-11-27', 'consumption': 0,   'cost': 0},
                    {'date': '2025-12-27', 'invoiceFrom': '2025-11-28', 'invoiceTo': '2025-12-27', 'consumption': 493, 'cost': 165.11},
                    {'date': '2026-01-30', 'invoiceFrom': '2025-12-28', 'invoiceTo': '2026-01-30', 'consumption': 0,   'cost': 0},
                    {'date': '2026-02-26', 'invoiceFrom': '2026-01-31', 'invoiceTo': '2026-02-26', 'consumption': 397, 'cost': 139.20},
                    {'date': '2026-03-27', 'invoiceFrom': '2026-02-27', 'invoiceTo': '2026-03-27', 'consumption': 0,   'cost': 0},
                ]},
                {'label': 'actual', 'data': [
                    {'date': '2025-07-01', 'invoiceFrom': '2025-06-14', 'invoiceTo': '2025-07-01', 'consumption': 324, 'cost': 91.08},
                    {'date': '2025-07-30', 'invoiceFrom': '2025-07-02', 'invoiceTo': '2025-07-30', 'consumption': 0,   'cost': 0},
                    {'date': '2025-08-29', 'invoiceFrom': '2025-07-31', 'invoiceTo': '2025-08-29', 'consumption': 539, 'cost': 151.61},
                    {'date': '2025-09-30', 'invoiceFrom': '2025-08-30', 'invoiceTo': '2025-09-30', 'consumption': 0,   'cost': 0},
                    {'date': '2025-10-30', 'invoiceFrom': '2025-10-01', 'invoiceTo': '2025-10-30', 'consumption': 635, 'cost': 193.68},
                    {'date': '2025-11-27', 'invoiceFrom': '2025-10-31', 'invoiceTo': '2025-11-27', 'consumption': 463, 'cost': 154.67},
                    {'date': '2025-12-27', 'invoiceFrom': '2025-11-28', 'invoiceTo': '2025-12-27', 'consumption': 0,   'cost': 0},
                    {'date': '2026-01-30', 'invoiceFrom': '2025-12-28', 'invoiceTo': '2026-01-30', 'consumption': 443, 'cost': 163.84},
                    {'date': '2026-02-26', 'invoiceFrom': '2026-01-31', 'invoiceTo': '2026-02-26', 'consumption': 0,   'cost': 0},
                    {'date': '2026-03-27', 'invoiceFrom': '2026-02-27', 'invoiceTo': '2026-03-27', 'consumption': 460, 'cost': 156.28},
                ]},
            ],
        }

    def test_collapses_to_one_entry_per_period(self, real_gas_monthly_response):
        usage = GasUsage(real_gas_monthly_response)
        assert len(usage.daily_usage) == 20  # 10 periods × 2 groups
        assert len(usage.consumption_periods) == 10  # collapsed

    def test_consumption_periods_sum_matches_total_usage(self, real_gas_monthly_response):
        usage = GasUsage(real_gas_monthly_response)
        # Iterating consumption_periods gives the SAME total without
        # double-counting or losing values to the pair-overwrite trap.
        period_sum = sum(p.get('consumption') or 0 for p in usage.consumption_periods)
        assert period_sum == usage.total_usage
        assert period_sum == 4842

    def test_estimated_periods_keep_real_value_and_tag(self, real_gas_monthly_response):
        usage = GasUsage(real_gas_monthly_response)
        feb = next(p for p in usage.consumption_periods if p['invoice_to'] == '2026-02-26')
        assert feb['consumption'] == 397.0  # NOT 0 (the actual pair partner)
        assert feb['is_estimated'] is True
        assert feb['read_type'] == 'estimate'

    def test_actual_periods_pick_actual_over_zero_estimate(self, real_gas_monthly_response):
        usage = GasUsage(real_gas_monthly_response)
        mar = next(p for p in usage.consumption_periods if p['invoice_to'] == '2026-03-27')
        assert mar['consumption'] == 460.0
        assert mar['is_estimated'] is False
        assert mar['read_type'] == 'actual'

    def test_chronological_order(self, real_gas_monthly_response):
        usage = GasUsage(real_gas_monthly_response)
        invoice_tos = [p['invoice_to'] for p in usage.consumption_periods]
        assert invoice_tos == sorted(invoice_tos)
        # Specifically the user-reported reference dates:
        assert '2026-01-30' in invoice_tos
        assert '2026-02-26' in invoice_tos
        assert '2026-03-27' in invoice_tos

    def test_empty_usage_returns_empty_list(self):
        usage = ServiceUsage({'usage': []})
        assert usage.consumption_periods == []

    def test_actual_only_response_unchanged(self):
        # Electricity-style payload (only 'actual' group). consumption_periods
        # should produce the same list as daily_usage.
        data = {
            'usage': [{'label': 'actual', 'data': [
                {'date': '2026-01-01', 'invoiceFrom': '2026-01-01', 'invoiceTo': '2026-01-01', 'consumption': 5, 'cost': 1},
                {'date': '2026-01-02', 'invoiceFrom': '2026-01-02', 'invoiceTo': '2026-01-02', 'consumption': 7, 'cost': 1.5},
            ]}]
        }
        usage = ServiceUsage(data)
        assert len(usage.consumption_periods) == 2
        assert [p['consumption'] for p in usage.consumption_periods] == [5, 7]
        assert all(not p['is_estimated'] for p in usage.consumption_periods)

    def test_tie_breaker_prefers_actual_over_estimate(self):
        # Pair both with the same non-zero value (Mercury correction scenario).
        # Convention: actual wins. (Real-world non-zero estimate + non-zero
        # actual in the same period suggests Mercury revised the read; the
        # actual is authoritative.)
        data = {
            'usage': [
                {'label': 'estimate', 'data': [{'date': '2026-01-01', 'invoiceTo': '2026-01-01', 'consumption': 100, 'cost': 30}]},
                {'label': 'actual',   'data': [{'date': '2026-01-01', 'invoiceTo': '2026-01-01', 'consumption': 100, 'cost': 30}]},
            ]
        }
        usage = ServiceUsage(data)
        assert len(usage.consumption_periods) == 1
        assert usage.consumption_periods[0]['is_estimated'] is False
        assert usage.consumption_periods[0]['read_type'] == 'actual'

    def test_picks_larger_non_zero_when_both_have_values(self):
        # Defensive: if Mercury ever sends both with different non-zero values,
        # pick the larger (likely the corrected/finalized read).
        data = {
            'usage': [
                {'label': 'estimate', 'data': [{'date': '2026-01-01', 'invoiceTo': '2026-01-01', 'consumption': 50, 'cost': 15}]},
                {'label': 'actual',   'data': [{'date': '2026-01-01', 'invoiceTo': '2026-01-01', 'consumption': 75, 'cost': 22}]},
            ]
        }
        usage = ServiceUsage(data)
        assert len(usage.consumption_periods) == 1
        assert usage.consumption_periods[0]['consumption'] == 75
        assert usage.consumption_periods[0]['is_estimated'] is False
```

---

### Step 3 — Demo the new property in `mercury_examples.py`

**File**: `mercury_examples.py`
**Lines**: example_5a monthly section (after the existing `Sample Monthly Breakdown` block)
**Action**: UPDATE

```python
# Show the collapsed view alongside the raw daily_usage breakdown.
if hasattr(monthly_gas, 'consumption_periods'):
    periods = monthly_gas.consumption_periods
    print(f"   📊 Consumption Periods (collapsed pair view, {len(periods)} entries):")
    for i, p in enumerate(periods[-6:], 1):
        invoice_to = (p.get('invoice_to') or p.get('date') or '?')[:10]
        consumption = p.get('consumption') or 0
        cost = p.get('cost') or 0
        marker = ' (estimated)' if p.get('is_estimated') else ''
        print(f"      {i}. {invoice_to}: {consumption:.2f} units{marker} (${cost:.2f})")
```

The collapsed view is what HA-style downstream consumers should be iterating; the raw `daily_usage` block is kept for transparency/debugging.

---

### Step 4 — Document the cross-repo implication

**File**: `pymercury/api/models/base.py` (docstring on the new property — already in Step 1)
**Action**: include a one-line note that this is the recommended consumer surface.

No standalone changelog file in this repo; the Step 5 commit message is the durable record.

---

### Step 5 — HA-side fix (out of scope for this artifact, recorded for the user)

**Repo**: `home-assistant-mercury-co-nz` (separate)
**File**: `custom_components/mercury_co_nz/mercury_api.py:982`
**Action**: replace the `daily_usage` consumption with `consumption_periods` once pymercury 1.1.3 ships:

```python
# Before
monthly_history = list(getattr(gas_monthly, "daily_usage", []) or [])

# After (requires pymercury >= 1.1.3)
monthly_history = list(getattr(gas_monthly, "consumption_periods", []) or [])
```

And in `statistics.py:255-298`, the bucketize-then-overwrite block disappears entirely:

```python
# Before
buckets: dict[datetime, tuple[float, float]] = {}
for record in monthly_records or []:
    ...
    buckets[anchor] = (float(consumption), float(cost))   # last-write-wins bug
sorted_anchors = [a for a in sorted(buckets.keys()) if a.timestamp() > cutoff_ts]
energy_running = float(energy_sum_start or 0.0)
...
for anchor in sorted_anchors:
    kwh, cost = buckets[anchor]
    ...

# After
energy_running = float(energy_sum_start or 0.0)
cost_running = float(cost_sum_start or 0.0)
energy_stats: list[StatisticData] = []
cost_stats: list[StatisticData] = []
for record in monthly_records or []:
    invoice_to_raw = record.get("invoice_to") or record.get("date")
    if not isinstance(invoice_to_raw, str):
        skipped += 1; continue
    anchor = MercuryStatisticsImporter._parse_invoice_end_utc(invoice_to_raw)
    if anchor is None or anchor.timestamp() <= cutoff_ts:
        skipped += 1; continue
    kwh = record.get("consumption")
    cost = record.get("cost")
    if kwh is None or cost is None:
        skipped += 1; continue
    energy_running += float(kwh)
    cost_running += float(cost)
    energy_stats.append(StatisticData(start=anchor, state=float(kwh), sum=energy_running))
    cost_stats.append(StatisticData(start=anchor, state=float(cost), sum=cost_running))
```

Plus a ONE-TIME reconciliation: the user should manually `clear_statistics` for the gas energy + cost statistic IDs in HA Developer Tools, then re-import. Otherwise the existing 164,220 ghost stays in the recorder DB.

---

## Patterns to Follow

**Mirror the property style of existing properties on adjacent models**:

```python
# SOURCE: pymercury/api/models/electricity.py:182-186
self.latest_reading_value = primary_register.get('lastReading')
self.latest_reading_date  = primary_register.get('lastReadDate')
```

(plain attributes assigned in `__init__`). The new `consumption_periods` is intentionally a `@property` instead of a precomputed attribute because it's a transformation over `daily_usage` and adding it to `__init__` would re-trigger any test that snapshots `vars(usage)`. Property is also lazy — `__init__` cost stays the same.

**Mirror the test fixture style**:

```python
# SOURCE: tests/test_models_usage.py existing TestServiceUsage class
def test_multiple_usage_arrays(self):
    data = {'serviceType': 'Gas', 'usagePeriod': 'Monthly', 'usage': [...]}
    usage = ServiceUsage(data)
    assert len(usage.usage_data) == 3
    ...
```

`TestConsumptionPeriods` uses a pytest fixture for the real-shape capture so multiple tests share it.

---

## Edge Cases & Risks

| Risk / Edge Case | Mitigation |
|---|---|
| Mercury starts emitting both groups with non-zero values for the same period (correction issued mid-month) | Tie-breaker prefers `actual`; `test_tie_breaker_prefers_actual_over_estimate` and `test_picks_larger_non_zero_when_both_have_values` cover this. |
| A period has neither `invoice_from` nor `invoice_to` (flat-list shape; some endpoints) | Group key falls back to `date`; flat-list electricity payloads collapse 1-to-1 with no behavior change. `test_actual_only_response_unchanged` covers this. |
| `consumption_periods` is called repeatedly on a hot path (HA polls every 30 mins) | Property recomputes on every access, but the work is O(n) on `daily_usage` (typically ≤ 30 entries). For HA's polling cadence this is negligible — under 1ms. If profiling later shows hot-spotting, cache via `functools.cached_property` (py3.8+ — already supported by the project). |
| Electricity payload happens to have an `estimate` group (rare but possible) | The collapse logic is service-agnostic; it just collapses `(invoice_to, invoice_from)` pairs. If electricity emits both, the collapse picks the larger/actual — same correctness as for gas. |
| Caller iterates `daily_usage` AND `consumption_periods` for the same usage object | Both work; numbers reconcile (sum matches `total_usage`). Documented in the property docstring. |
| The HA-side "stale 164,220" data persists after pymercury 1.1.3 ships (recorder DB doesn't auto-recover) | Out-of-scope for pymercury but documented in Step 5. User clears the statistic_id in HA Dev Tools and re-imports. |

---

## Validation

### Automated

```bash
cd /var/www/personal/pymercury
/tmp/pymercury_venv/bin/pytest tests/ -q --no-cov
/tmp/pymercury_venv/bin/pytest tests/test_models_usage.py::TestConsumptionPeriods -v
/tmp/pymercury_venv/bin/pytest --cov=pymercury --cov-branch --cov-fail-under=100
```

**EXPECT**: 367 → 376+ tests pass (9 new). Coverage stays at 100%.

### Manual (against the user's account)

```bash
/tmp/pymercury_venv/bin/python3 -c "
from dotenv import dotenv_values
import sys; sys.path.insert(0, '/var/www/personal/pymercury')
from pymercury import MercuryClient

cfg = dotenv_values('/var/www/personal/pymercury/.env')
c = MercuryClient(cfg['MERCURY_EMAIL'], cfg['MERCURY_PASSWORD'])
c.login()
data = c.get_complete_account_data()
m = c.api.get_gas_usage_monthly(data.customer_id, data.account_ids[0], data.service_ids.gas[0])

print('daily_usage entries:', len(m.daily_usage))           # expect 20
print('consumption_periods entries:', len(m.consumption_periods))  # expect 10
print('Sum reconciles:', sum(p['consumption'] or 0 for p in m.consumption_periods) == m.total_usage)

# 27 March specifically
mar = next(p for p in m.consumption_periods if p['invoice_to'].startswith('2026-03-27'))
print('27 March:', mar['consumption'], 'kWh, is_estimated=', mar['is_estimated'])  # expect 460, False

# 26 February — the previously-lost estimate
feb = next(p for p in m.consumption_periods if p['invoice_to'].startswith('2026-02-26'))
print('26 February:', feb['consumption'], 'kWh, is_estimated=', feb['is_estimated'])  # expect 397, True
"
```

**EXPECT**: 20 daily_usage entries → 10 consumption_periods. Sum reconciles. 27 Mar = 460/actual, 26 Feb = 397/estimate (the value the HA integration was losing).

---

## Scope Boundaries

**IN SCOPE (this artifact, in pymercury repo):**

- `consumption_periods` property on `ServiceUsage` (Step 1).
- Tests using sanitized real-shape fixture (Step 2).
- `mercury_examples.py` demo of the new property (Step 3).

**OUT OF SCOPE:**

- Fixing `home-assistant-mercury-co-nz/custom_components/mercury_co_nz/statistics.py:259-273` — different repo. Step 5 documents the recommended downstream change for when 1.1.3 ships.
- Reconciling existing HA recorder data showing 164,220 — that's a one-time `clear_statistics` operation in HA Dev Tools; pymercury can't fix already-written recorder rows.
- Wiring `gas_meter_reads` into pymercury — the endpoint exists (`/services/gas/{service_id}/meter-reads` returns 200 OK with `[]` for this account), but is empty for the user's account so adding it now ships dead code. File for v1.2.0 or later.
- Changing `daily_usage` semantics (e.g., dropping zero-pair partners). That would be a breaking change for existing consumers who expect 1:1 mapping with Mercury's groups. Add `consumption_periods` as a parallel surface; let downstream choose.
- Async support, Pydantic models, etc. — already deferred to v2.0.0.

---

## Metadata

- **Investigated by**: Claude
- **Timestamp**: 2026-04-28
- **Artifact**: `.claude/PRPs/issues/investigation-gas-164220-ha-recurrence.md`
- **Live capture**: `/tmp/gas_probe.json` (sanitized; 20 entries, total_usage=4842, max=635)
- **Auxiliary captures**: `/tmp/gas_probe2.json` (daily/hourly/march-window — all empty), `/tmp/gas_probe3.json` (gas_meter_reads endpoint exists but returns `[]`).
- **Related artifacts**:
  - `.claude/PRPs/issues/completed/investigation-gas-empty-output.md` — closed by PR #3 (envelope detection).
  - `.claude/PRPs/issues/completed/investigation-gas-bad-values-and-missing-estimates.md` — closed by PR #5 + #6 (estimate-merge + B3 hardening).
- **HA-side bug location** (not fixable from pymercury): `home-assistant-mercury-co-nz/custom_components/mercury_co_nz/statistics.py:255-298`.
- **Confidence**: HIGH for the data shape and the HA-side overwrite mechanism; MEDIUM for the exact `460 × 357 = 164,220` arithmetic (likely an HA recorder dedup failure; verifying would require instrumenting HA's `async_add_external_statistics` path which is out of scope here).
