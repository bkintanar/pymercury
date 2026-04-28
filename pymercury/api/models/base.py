#!/usr/bin/env python3
"""
Base Models for Mercury.co.nz API

Contains shared base classes and common functionality.
"""

import os
import sys
from typing import Dict, Any, List


# Top-level envelope keys Mercury has been observed (or plausibly may) use
# for usage data. Order matters: try the canonical 'usage' first to preserve
# existing behavior, then alternatives.
_USAGE_ENVELOPE_KEYS = (
    'usage',
    'monthlyUsage',
    'hourlyUsage',
    'dailyUsage',
    'consumption',
    'usageData',
    'data',
)


def _extract_usage_arrays(data: Dict[str, Any]) -> List[Any]:
    """Find the usage_arrays envelope in a Mercury usage response.

    Mercury's electricity endpoint returns ``{"usage": [{"label":"actual","data":[...]}]}``.
    Other intervals / services may use a different top-level key. This
    helper scans known alternatives and returns the first non-empty list.
    """
    for key in _USAGE_ENVELOPE_KEYS:
        candidate = data.get(key)
        if isinstance(candidate, list) and candidate:
            return candidate
    # Some endpoints may put usage points under a nested summary key.
    for nested_key in ('monthlySummary', 'weeklySummary', 'dailySummary', 'summary'):
        nested = data.get(nested_key)
        if isinstance(nested, dict):
            inner = nested.get('usage')
            if isinstance(inner, list) and inner:
                return inner
    return []


def _envelope_present(data: Dict[str, Any]) -> bool:
    """Check whether a known envelope key is present at top level — even if empty.

    Used to distinguish "Mercury returned an empty usage array" (no warning
    needed) from "Mercury returned a shape we don't recognize" (warn so the
    user can see the actual top-level keys).
    """
    if not isinstance(data, dict):
        return False
    if any(k in data for k in _USAGE_ENVELOPE_KEYS):
        return True
    for nk in ('monthlySummary', 'weeklySummary', 'dailySummary', 'summary'):
        nested = data.get(nk)
        if isinstance(nested, dict) and 'usage' in nested:
            return True
    return False


def _extract_usage_data(usage_arrays: List[Any]) -> List[Dict[str, Any]]:
    """From a list of usage groups (or a flat list of usage points), return
    the list of individual usage points. Handles three observed shapes:

    1. ``[{"label":"actual","data":[<points>]}, {"label":"estimate",...}]``
       — merge both groups so estimated entries (Mercury's gap-fillers
       between actual meter reads — common for piped gas read every 2-3
       months) are visible to downstream consumers, not silently dropped.
       Each merged point is tagged with ``is_estimated`` (bool) and
       ``read_type`` (raw label string) so callers can distinguish.
    2. ``[{"label":"actual","data":[<points>]}]`` with only one group.
    3. ``[<point>, <point>, ...]`` — a flat list with no group wrapper.
    """
    if not usage_arrays:
        return []
    first = usage_arrays[0]
    # Shape 3: flat list of usage points (no label/data wrapper)
    if isinstance(first, dict) and ('consumption' in first or 'usage' in first or 'date' in first):
        # Heuristic: looks like a usage point already
        if 'data' not in first or not isinstance(first.get('data'), list):
            return [p for p in usage_arrays if isinstance(p, dict)]
    # Shapes 1 & 2: groups with label + data. Merge ONLY groups whose
    # label is a known per-period reading source (actual / estimate /
    # estimated, or no label at all). Skip groups labeled 'summary',
    # 'forecast', 'projected', etc. — those carry totalizers or
    # forward-looking values, not per-period readings, and would pollute
    # the merged series with cumulative-style numbers (the suspected
    # cause of the unrelated 158240-vs-460 anomaly being investigated
    # separately). A conservative allowlist matches the prior code's
    # behavior of only consuming 'actual' while now also keeping
    # 'estimate' for the dropped-estimates fix.
    known_data_labels = {'actual', 'estimate', 'estimated'}
    groups_with_data = [
        g for g in usage_arrays
        if isinstance(g, dict)
        and isinstance(g.get('data'), list)
        and (g.get('label') is None or g.get('label') in known_data_labels)
    ]
    merged: List[Dict[str, Any]] = []
    for group in groups_with_data:
        label = group.get('label')
        for point in group.get('data', []) or []:
            if not isinstance(point, dict):
                continue
            tagged = dict(point)
            # setdefault: a server-sent 'is_estimated' on the point wins
            # over the group label. Today no Mercury fixture does this;
            # the path is intentional forward-compat for a future shape.
            tagged.setdefault('is_estimated', label in ('estimate', 'estimated'))
            tagged.setdefault('read_type', label)
            merged.append(tagged)
    merged.sort(key=lambda p: p.get('date') or '')
    return merged


def _emit_empty_usage_warning(data: Dict[str, Any]) -> None:
    """When a 200 response yields no usage points, print one diagnostic line
    so users can see Mercury's actual envelope. Suppress with
    ``MERCURY_NO_USAGE_DIAG=1`` in the environment.
    """
    if os.environ.get('MERCURY_NO_USAGE_DIAG'):
        return
    keys = sorted(data.keys()) if isinstance(data, dict) else type(data).__name__
    msg = f"⚠️ ServiceUsage parsed 0 usage points; Mercury response top-level keys = {keys}"
    print(msg, file=sys.stderr)


class ServiceUsage:
    """Generic service usage data container for electricity, gas, etc."""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.service_type = data.get('serviceType')
        self.usage_period = data.get('usagePeriod')  # Daily, Hourly, Monthly
        self.start_date = data.get('startDate')
        self.end_date = data.get('endDate')

        # Extract usage data from Mercury.co.nz API format. Mercury's gas and
        # electricity responses can use different top-level envelope keys
        # (e.g. 'usage' vs 'monthlyUsage'). _extract_usage_arrays scans
        # known alternatives.
        usage_arrays = _extract_usage_arrays(data)
        self.usage_data = _extract_usage_data(usage_arrays)

        # Diagnostic: if a parse came up empty AND we didn't recognize any
        # envelope key, emit one stderr line so users can see Mercury's real
        # envelope shape. Only fires from the base class (subclass __init__
        # calls go silent — avoids double-firing when get_gas_usage wraps
        # ServiceUsage as GasUsage). An empty-but-recognized envelope means
        # Mercury returned no data for the window, not a parser bug — silent.
        if not self.usage_data and not _envelope_present(data) and type(self) is ServiceUsage:
            _emit_empty_usage_warning(data)

        # Store all usage arrays for access to estimates, etc.
        self.all_usage_arrays = usage_arrays

        # Calculate statistics from usage data
        if self.usage_data:
            consumptions = [point.get('consumption', 0) for point in self.usage_data]
            costs = [point.get('cost', 0) for point in self.usage_data]

            self.total_usage = sum(consumptions)
            self.total_cost = sum(costs)
            self.average_daily_usage = self.total_usage / len(consumptions) if consumptions else 0
            self.max_daily_usage = max(consumptions) if consumptions else 0
            self.min_daily_usage = min(consumptions) if consumptions else 0
            self.data_points = len(self.usage_data)
        else:
            self.total_usage = 0
            self.total_cost = 0
            self.average_daily_usage = 0
            self.max_daily_usage = 0
            self.min_daily_usage = 0
            self.data_points = 0

        # Temperature data (Mercury.co.nz returns this separately)
        # Note: Temperature data is only available for electricity and daily intervals
        temp_data = data.get('averageTemperature')
        if temp_data and isinstance(temp_data, dict):
            self.temperature_data = temp_data.get('data', [])
        else:
            self.temperature_data = []

        # Calculate average temperature
        if self.temperature_data:
            temps = [point.get('temp', 0) for point in self.temperature_data]
            self.average_temperature = sum(temps) / len(temps) if temps else 0
        else:
            self.average_temperature = None

        # Usage breakdown by time period
        self.daily_usage = []
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

        # Legacy fields for backward compatibility
        self.service_id = data.get('serviceId')
        self.account_id = data.get('accountId')
        self.interval = self.usage_period.lower() if self.usage_period else 'daily'
        self.period_start = self.start_date
        self.period_end = self.end_date
        self.days_in_period = len(self.usage_data) if self.usage_data else 0

        # Store annotations field
        self.annotations = data.get('annotations', [])

    @property
    def consumption_periods(self) -> List[Dict[str, Any]]:
        """One entry per billing period — collapses the estimate+actual pair.

        Mercury returns gas (and possibly other) usage as two parallel groups:
        ``estimate`` and ``actual``. For each billing period both groups emit
        a record at the same ``(invoice_from, invoice_to)`` window, but only
        ONE has a non-zero consumption — the other is a zero placeholder.
        Iterating ``daily_usage`` directly gives consumers double the rows
        and forces them to handle the pair structure themselves; bucketize-
        by-anchor with a naive ``dict[anchor] = ...`` assignment causes the
        second-written entry to clobber the first, losing the real value
        for either estimated or actual months depending on group order.

        This property collapses each pair to a single entry by grouping on
        ``(invoice_from, invoice_to)`` (or ``date`` when invoice fields are
        absent for flat-shape compatibility) and picking the entry with the
        largest non-zero consumption. Ties are broken by preferring
        ``actual`` over ``estimate`` (matches the convention that an actual
        meter reading authoritatively supersedes an estimate, including the
        zero/zero pair where both consumptions are 0). Returned in
        chronological order by invoice end date.

        Recommended consumer surface for downstream tools (e.g., Home
        Assistant statistics importers) so they don't have to walk the
        parallel-pair structure themselves.
        """
        if not self.daily_usage:
            return []

        from collections import defaultdict
        grouped: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for entry in self.daily_usage:
            key = (
                entry.get('invoice_from') or '',
                entry.get('invoice_to') or entry.get('date') or '',
            )
            grouped[key].append(entry)

        def _rank(e: Dict[str, Any]) -> tuple:
            # (-consumption: bigger first; estimated last on ties so actual wins)
            consumption = e.get('consumption') or 0
            return (-float(consumption), 1 if e.get('is_estimated') else 0)

        collapsed: List[Dict[str, Any]] = []
        for entries in grouped.values():
            if len(entries) == 1:
                collapsed.append(entries[0])
            else:
                collapsed.append(sorted(entries, key=_rank)[0])

        collapsed.sort(key=lambda d: d.get('invoice_to') or d.get('date') or '')
        return collapsed
