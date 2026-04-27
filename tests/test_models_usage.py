#!/usr/bin/env python3
"""
Unit tests for usage models in pymercury.api.models (base, electricity, gas)
"""

import pytest
from pymercury.api.models.base import (
    ServiceUsage,
    _extract_usage_arrays,
    _extract_usage_data,
    _emit_empty_usage_warning,
    _envelope_present,
)
from pymercury.api.models.electricity import ElectricityUsage
from pymercury.api.models.gas import GasUsage


class TestExtractUsageArrays:
    """Test the envelope-detection helper that scans for the usage arrays."""

    def test_canonical_usage_key(self):
        data = {"usage": [{"label": "actual", "data": [{"consumption": 1}]}]}
        assert _extract_usage_arrays(data) == data["usage"]

    def test_alternative_top_level_keys(self):
        # Mercury's gas response may use a different envelope key.
        for key in ("monthlyUsage", "hourlyUsage", "dailyUsage", "consumption", "usageData", "data"):
            data = {key: [{"consumption": 5, "date": "2026-01-01"}]}
            assert _extract_usage_arrays(data) == data[key], f"failed for key {key}"

    def test_nested_summary_usage(self):
        # Some endpoints nest usage under a summary key (like electricity_summary).
        data = {"monthlySummary": {"usage": [{"consumption": 7}]}}
        assert _extract_usage_arrays(data) == [{"consumption": 7}]

    def test_returns_empty_when_nothing_matches(self):
        assert _extract_usage_arrays({"unrelated": "stuff"}) == []
        assert _extract_usage_arrays({}) == []
        # Empty list under a known key still returns []
        assert _extract_usage_arrays({"usage": []}) == []

    def test_returns_empty_when_value_is_not_a_list(self):
        # Non-list value at envelope key should be skipped
        assert _extract_usage_arrays({"usage": "not a list"}) == []


class TestExtractUsageData:
    """Test the usage-points extraction across the three observed shapes."""

    def test_grouped_with_actual_label(self):
        groups = [
            {"label": "estimate", "data": [{"consumption": 1}]},
            {"label": "actual", "data": [{"consumption": 10}, {"consumption": 20}]},
        ]
        assert _extract_usage_data(groups) == [{"consumption": 10}, {"consumption": 20}]

    def test_grouped_without_actual_falls_back_to_first(self):
        groups = [
            {"label": "estimate", "data": [{"consumption": 5}]},
            {"label": "forecast", "data": [{"consumption": 6}]},
        ]
        assert _extract_usage_data(groups) == [{"consumption": 5}]

    def test_flat_list_of_usage_points(self):
        # No label/data wrapper — just a list of usage points directly.
        flat = [
            {"date": "2026-01-01", "consumption": 5},
            {"date": "2026-01-02", "consumption": 7},
        ]
        assert _extract_usage_data(flat) == flat

    def test_empty_input(self):
        assert _extract_usage_data([]) == []

    def test_first_item_not_a_dict(self):
        # Non-dict first element triggers the final fallback (returns []).
        assert _extract_usage_data(["not a dict"]) == []

    def test_first_item_dict_with_data_key_is_a_group(self):
        # Heuristic: if first dict has 'data' as a list, treat as group.
        groups = [{"label": "actual", "data": [{"consumption": 99}]}]
        assert _extract_usage_data(groups) == [{"consumption": 99}]

    def test_first_item_has_usage_keys_AND_data_list_treated_as_group(self):
        # Edge case: a group dict that ALSO has 'date' or 'consumption' on it
        # (some endpoints embed usage-point-like fields on the group). The
        # heuristic should still treat it as a group because it has a 'data' list.
        groups = [{"date": "2026-01-01", "data": [{"consumption": 42}]}]
        # Falls through to the actual-label / first-group fallback.
        assert _extract_usage_data(groups) == [{"consumption": 42}]


class TestExtractUsageArraysNestedNonDict:
    """Cover the `if isinstance(nested, dict)` False branch in _extract_usage_arrays."""

    def test_nested_summary_key_is_not_a_dict(self):
        # data['monthlySummary'] is a string, not a dict — the inner check skips it.
        assert _extract_usage_arrays({"monthlySummary": "not a dict"}) == []

    def test_nested_summary_dict_with_empty_usage_continues_loop(self):
        # monthlySummary is a dict but its 'usage' is empty — loop continues
        # to next nested_key and ultimately returns [].
        assert _extract_usage_arrays({"monthlySummary": {"usage": []}}) == []


class TestEnvelopePresent:
    """Test the helper that distinguishes 'empty but recognized' from 'unrecognized'."""

    def test_top_level_envelope_key_present_even_if_empty(self):
        # 'usage' key with empty list — envelope IS recognized.
        assert _envelope_present({"usage": []}) is True
        # 'usage' key absent — not recognized.
        assert _envelope_present({"unrelated": 1}) is False

    def test_nested_summary_envelope_recognized(self):
        # monthlySummary is a dict with 'usage' inside — recognized even if empty.
        assert _envelope_present({"monthlySummary": {"usage": []}}) is True

    def test_nested_summary_without_usage_key_not_recognized(self):
        # monthlySummary present but lacks 'usage' inner — not recognized.
        assert _envelope_present({"monthlySummary": {"otherStuff": []}}) is False

    def test_non_dict_input_not_recognized(self):
        assert _envelope_present("not a dict") is False
        assert _envelope_present([1, 2, 3]) is False
        assert _envelope_present(None) is False


class TestServiceUsageWarningGating:
    """Test that the empty-usage warning fires only when truly unrecognized."""

    def test_warning_silent_when_envelope_present_but_empty(self, capsys):
        # Mercury returned the canonical envelope but no data points.
        # That's a normal "no readings in window" response — no warning.
        ServiceUsage({"usage": [], "serviceType": "Gas"})
        assert capsys.readouterr().err == ""

    def test_warning_fires_when_no_envelope_recognized(self, capsys):
        ServiceUsage({"completelyDifferentShape": "value"})
        assert "ServiceUsage parsed 0 usage points" in capsys.readouterr().err

    def test_warning_silent_for_subclass_construction(self, capsys):
        # GasUsage / ElectricityUsage construction shouldn't double-fire the
        # warning (avoids noise when get_gas_usage wraps ServiceUsage).
        from pymercury.api.models.gas import GasUsage
        GasUsage({"completelyDifferentShape": "value"})  # subclass — no warning
        assert capsys.readouterr().err == ""


class TestEmitEmptyUsageWarning:
    """Test the diagnostic warning emitted when no usage parses."""

    def test_warning_printed_to_stderr(self, capsys):
        _emit_empty_usage_warning({"foo": 1, "bar": 2})
        captured = capsys.readouterr()
        # Stdout is clean; stderr has the diag line.
        assert captured.out == ""
        assert "ServiceUsage parsed 0 usage points" in captured.err
        assert "['bar', 'foo']" in captured.err

    def test_warning_suppressed_by_env_var(self, capsys, monkeypatch):
        monkeypatch.setenv("MERCURY_NO_USAGE_DIAG", "1")
        _emit_empty_usage_warning({"foo": 1})
        assert capsys.readouterr().err == ""

    def test_warning_handles_non_dict(self, capsys):
        _emit_empty_usage_warning(["not a dict"])
        assert "list" in capsys.readouterr().err


class TestServiceUsage:
    """Test ServiceUsage base class"""

    def test_basic_initialization(self):
        """Test basic ServiceUsage initialization"""
        data = {
            'serviceType': 'Electricity',
            'usagePeriod': 'Daily',
            'startDate': '2025-01-01T00:00:00+12:00',
            'endDate': '2025-01-10T00:00:00+12:00',
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 10.5, 'cost': 5.25},
                        {'date': '2025-01-02', 'consumption': 8.3, 'cost': 4.15},
                        {'date': '2025-01-03', 'consumption': 12.1, 'cost': 6.05}
                    ]
                }
            ]
        }

        usage = ServiceUsage(data)

        assert usage.service_type == 'Electricity'
        assert usage.usage_period == 'Daily'
        assert usage.start_date == '2025-01-01T00:00:00+12:00'
        assert usage.end_date == '2025-01-10T00:00:00+12:00'
        assert len(usage.usage_data) == 3
        assert usage.total_usage == 30.9  # 10.5 + 8.3 + 12.1
        assert usage.total_cost == 15.45   # 5.25 + 4.15 + 6.05
        assert usage.data_points == 3
        assert usage.max_daily_usage == 12.1
        assert usage.min_daily_usage == 8.3
        assert abs(usage.average_daily_usage - 10.3) < 0.01  # 30.9 / 3 (handle floating point precision)

    def test_multiple_usage_arrays(self):
        """Test ServiceUsage with multiple usage arrays (actual, estimate)"""
        data = {
            'serviceType': 'Gas',
            'usagePeriod': 'Daily',
            'usage': [
                {
                    'label': 'estimate',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 5.0, 'cost': 2.5}
                    ]
                },
                {
                    'label': 'actual',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 10.0, 'cost': 5.0}
                    ]
                }
            ]
        }

        usage = ServiceUsage(data)

        # Should prefer 'actual' data
        assert len(usage.usage_data) == 1
        assert usage.usage_data[0]['consumption'] == 10.0
        assert usage.total_usage == 10.0
        assert len(usage.all_usage_arrays) == 2

    def test_no_actual_data(self):
        """Test ServiceUsage when no 'actual' data available"""
        data = {
            'serviceType': 'Electricity',
            'usage': [
                {
                    'label': 'estimate',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 5.0, 'cost': 2.5}
                    ]
                }
            ]
        }

        usage = ServiceUsage(data)

        # Should use first available array when no 'actual' found
        assert len(usage.usage_data) == 1
        assert usage.usage_data[0]['consumption'] == 5.0
        assert usage.total_usage == 5.0

    def test_empty_usage_data(self):
        """Test ServiceUsage with empty usage data"""
        data = {
            'serviceType': 'Gas',
            'usagePeriod': 'Daily',
            'usage': []
        }

        usage = ServiceUsage(data)

        assert usage.usage_data == []
        assert usage.total_usage == 0
        assert usage.total_cost == 0
        assert usage.data_points == 0
        assert usage.max_daily_usage == 0
        assert usage.min_daily_usage == 0
        assert usage.average_daily_usage == 0

    def test_temperature_data(self):
        """Test ServiceUsage with temperature data (electricity only)"""
        data = {
            'serviceType': 'Electricity',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 10.0}]
                }
            ],
            'averageTemperature': {
                'data': [
                    {'temp': 15.5},
                    {'temp': 18.2},
                    {'temp': 16.8}
                ]
            }
        }

        usage = ServiceUsage(data)

        assert len(usage.temperature_data) == 3
        assert usage.average_temperature == 16.833333333333332  # (15.5 + 18.2 + 16.8) / 3

    def test_no_temperature_data(self):
        """Test ServiceUsage without temperature data"""
        data = {
            'serviceType': 'Gas',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 10.0}]
                }
            ]
        }

        usage = ServiceUsage(data)

        assert usage.temperature_data == []
        assert usage.average_temperature is None

    def test_daily_usage_breakdown(self):
        """Test ServiceUsage daily usage breakdown"""
        data = {
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {
                            'date': '2025-01-01',
                            'consumption': 10.0,
                            'cost': 5.0,
                            'freePower': 0.5,
                            'invoiceFrom': '2025-01-01',
                            'invoiceTo': '2025-01-02'
                        }
                    ]
                }
            ]
        }

        usage = ServiceUsage(data)

        assert len(usage.daily_usage) == 1
        daily = usage.daily_usage[0]
        assert daily['date'] == '2025-01-01'
        assert daily['consumption'] == 10.0
        assert daily['cost'] == 5.0
        assert daily['free_power'] == 0.5
        assert daily['invoice_from'] == '2025-01-01'
        assert daily['invoice_to'] == '2025-01-02'

    def test_legacy_fields(self):
        """Test ServiceUsage legacy field mapping"""
        data = {
            'serviceId': 'E123456',
            'accountId': 'A789012',
            'usagePeriod': 'Hourly',
            'startDate': '2025-01-01',
            'endDate': '2025-01-02',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 1.0}, {'consumption': 2.0}]
                }
            ],
            'annotations': ['Note 1', 'Note 2']
        }

        usage = ServiceUsage(data)

        assert usage.service_id == 'E123456'
        assert usage.account_id == 'A789012'
        assert usage.interval == 'hourly'
        assert usage.period_start == '2025-01-01'
        assert usage.period_end == '2025-01-02'
        assert usage.days_in_period == 2
        assert usage.annotations == ['Note 1', 'Note 2']


class TestElectricityUsage:
    """Test ElectricityUsage inheritance"""

    def test_inheritance(self):
        """Test that ElectricityUsage inherits from ServiceUsage"""
        data = {
            'serviceType': 'Electricity',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 10.0, 'cost': 5.0}]
                }
            ]
        }

        electricity = ElectricityUsage(data)

        # Should be instance of both classes
        assert isinstance(electricity, ElectricityUsage)
        assert isinstance(electricity, ServiceUsage)

        # Should have all ServiceUsage functionality
        assert electricity.total_usage == 10.0
        assert electricity.total_cost == 5.0
        assert electricity.service_type == 'Electricity'

    def test_electricity_specific_behavior(self):
        """Test electricity-specific behavior (if any)"""
        data = {
            'serviceType': 'Electricity',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 15.5, 'cost': 7.75}]
                }
            ],
            'averageTemperature': {
                'data': [{'temp': 20.0}]
            }
        }

        electricity = ElectricityUsage(data)

        # Should handle temperature data (typical for electricity)
        assert electricity.average_temperature == 20.0


class TestGasUsage:
    """Test GasUsage inheritance"""

    def test_inheritance(self):
        """Test that GasUsage inherits from ServiceUsage"""
        data = {
            'serviceType': 'Gas',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 324.0, 'cost': 91.08}]
                }
            ]
        }

        gas = GasUsage(data)

        # Should be instance of both classes
        assert isinstance(gas, GasUsage)
        assert isinstance(gas, ServiceUsage)

        # Should have all ServiceUsage functionality
        assert gas.total_usage == 324.0
        assert gas.total_cost == 91.08
        assert gas.service_type == 'Gas'

    def test_gas_specific_behavior(self):
        """Test gas-specific behavior"""
        data = {
            'serviceType': 'Gas',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 100.0, 'cost': 50.0}]
                }
            ]
            # Note: No temperature data for gas
        }

        gas = GasUsage(data)

        # Gas typically doesn't have temperature data
        assert gas.average_temperature is None
        assert gas.temperature_data == []


class TestUsageComparison:
    """Test comparisons between different usage types"""

    def test_same_data_different_classes(self):
        """Test that same data produces same results across usage classes"""
        data = {
            'serviceType': 'TestService',
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {'consumption': 10.0, 'cost': 5.0},
                        {'consumption': 20.0, 'cost': 10.0}
                    ]
                }
            ]
        }

        base_usage = ServiceUsage(data)
        electricity_usage = ElectricityUsage(data)
        gas_usage = GasUsage(data)

        # All should have same calculated values
        for usage in [base_usage, electricity_usage, gas_usage]:
            assert usage.total_usage == 30.0
            assert usage.total_cost == 15.0
            assert usage.data_points == 2
            assert usage.max_daily_usage == 20.0
            assert usage.min_daily_usage == 10.0
            assert usage.average_daily_usage == 15.0
