#!/usr/bin/env python3
"""
Unit tests for usage models in pymercury.api.models (base, electricity, gas)
"""

import pytest
from pymercury.api.models.base import ServiceUsage
from pymercury.api.models.electricity import ElectricityUsage
from pymercury.api.models.gas import GasUsage


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
