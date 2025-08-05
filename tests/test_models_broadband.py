#!/usr/bin/env python3
"""
Unit tests for broadband models in pymercury.api.models.broadband
"""

import pytest
from pymercury.api.models.broadband import BroadbandUsage


class TestBroadbandUsage:
    """Test BroadbandUsage model"""

    def test_basic_initialization(self):
        """Test basic BroadbandUsage initialization with real data format"""
        data = {
            "avgDailyUsage": "8.55",
            "totalDataUsed": "42.73",
            "dailyUsages": [
                {
                    "date": "2025-08-01T00:00:00",
                    "usage": "10.02"
                },
                {
                    "date": "2025-08-02T00:00:00",
                    "usage": "10.20"
                },
                {
                    "date": "2025-08-03T00:00:00",
                    "usage": "6.11"
                },
                {
                    "date": "2025-08-04T00:00:00",
                    "usage": "13.80"
                },
                {
                    "date": "2025-08-05T00:00:00",
                    "usage": "2.60"
                },
                {
                    "date": "2025-08-06T00:00:00",
                    "usage": "0.00"
                }
            ],
            "planName": "FibreClassic Unlimited Naked",
            "planCode": "20398"
        }

        broadband = BroadbandUsage(data)

        # Test basic properties
        assert broadband.plan_name == "FibreClassic Unlimited Naked"
        assert broadband.plan_code == "20398"
        assert broadband.service_type == "Broadband"
        assert broadband.usage_period == "Daily"

        # Test numeric conversions
        assert broadband.avg_daily_usage == 8.55
        assert broadband.total_data_used == 42.73

        # Test calculated statistics
        assert broadband.max_daily_usage == 13.80
        assert broadband.min_daily_usage == 0.0
        assert broadband.data_points == 6
        assert broadband.usage_days == 5  # Days with non-zero usage

        # Test date range
        assert broadband.start_date == "2025-08-01T00:00:00"
        assert broadband.end_date == "2025-08-06T00:00:00"

        # Test raw data preservation
        assert broadband.raw_data == data
        assert len(broadband.daily_usages) == 6

    def test_empty_daily_usages(self):
        """Test BroadbandUsage with empty daily usages"""
        data = {
            "avgDailyUsage": "5.0",
            "totalDataUsed": "25.0",
            "dailyUsages": [],
            "planName": "Basic Plan",
            "planCode": "12345"
        }

        broadband = BroadbandUsage(data)

        assert broadband.avg_daily_usage == 5.0
        assert broadband.total_data_used == 25.0
        assert broadband.max_daily_usage == 0.0
        assert broadband.min_daily_usage == 0.0
        assert broadband.data_points == 0
        assert broadband.usage_days == 0
        assert broadband.start_date is None
        assert broadband.end_date is None

    def test_invalid_numeric_values(self):
        """Test BroadbandUsage with invalid numeric values"""
        data = {
            "avgDailyUsage": "invalid",
            "totalDataUsed": "",
            "dailyUsages": [
                {
                    "date": "2025-08-01T00:00:00",
                    "usage": "invalid"
                }
            ],
            "planName": "Test Plan",
            "planCode": "123"
        }

        broadband = BroadbandUsage(data)

        # Should handle invalid values gracefully
        assert broadband.avg_daily_usage == 0.0
        assert broadband.total_data_used == 0.0
        assert broadband.max_daily_usage == 0.0
        assert broadband.data_points == 0  # Invalid values result in 0 data points
        assert broadband.usage_days == 0  # No valid usage values

    def test_missing_plan_info(self):
        """Test BroadbandUsage with missing plan information"""
        data = {
            "avgDailyUsage": "10.0",
            "totalDataUsed": "50.0",
            "dailyUsages": []
        }

        broadband = BroadbandUsage(data)

        assert broadband.plan_name is None
        assert broadband.plan_code is None
        assert broadband.service_type == "Broadband"
        assert broadband.usage_period == "Daily"

    def test_zero_usage_days(self):
        """Test BroadbandUsage with all zero usage days"""
        data = {
            "avgDailyUsage": "0.0",
            "totalDataUsed": "0.0",
            "dailyUsages": [
                {"date": "2025-08-01T00:00:00", "usage": "0.0"},
                {"date": "2025-08-02T00:00:00", "usage": "0.0"},
                {"date": "2025-08-03T00:00:00", "usage": "0.0"}
            ],
            "planName": "Test Plan",
            "planCode": "123"
        }

        broadband = BroadbandUsage(data)

        assert broadband.data_points == 3
        assert broadband.usage_days == 0  # No non-zero usage days
        assert broadband.max_daily_usage == 0.0
        assert broadband.min_daily_usage == 0.0

    def test_mixed_usage_values(self):
        """Test BroadbandUsage with mixed usage values (some zero, some non-zero)"""
        data = {
            "avgDailyUsage": "5.0",
            "totalDataUsed": "20.0",
            "dailyUsages": [
                {"date": "2025-08-01T00:00:00", "usage": "10.0"},
                {"date": "2025-08-02T00:00:00", "usage": "0.0"},
                {"date": "2025-08-03T00:00:00", "usage": "5.0"},
                {"date": "2025-08-04T00:00:00", "usage": "0.0"},
                {"date": "2025-08-05T00:00:00", "usage": "15.0"}
            ],
            "planName": "Test Plan",
            "planCode": "123"
        }

        broadband = BroadbandUsage(data)

        assert broadband.data_points == 5
        assert broadband.usage_days == 3  # Three non-zero usage days
        assert broadband.max_daily_usage == 15.0
        assert broadband.min_daily_usage == 0.0

    def test_type_conversion_edge_cases(self):
        """Test BroadbandUsage with various type conversion edge cases"""
        data = {
            "avgDailyUsage": "10.5",  # String number
            "totalDataUsed": "25.0",   # String number
            "dailyUsages": [
                {"date": "2025-08-01T00:00:00", "usage": "5.5"},  # String number
                {"date": "2025-08-02T00:00:00", "usage": "0.0"}, # String zero
                {"date": "2025-08-03T00:00:00", "usage": "7.2"},  # String number
            ],
            "planName": "Test Plan",
            "planCode": "123"
        }

        broadband = BroadbandUsage(data)

        assert broadband.avg_daily_usage == 10.5
        assert broadband.total_data_used == 25.0
        assert broadband.data_points == 3
        assert broadband.usage_days == 2  # Two non-zero usage days
        assert broadband.max_daily_usage == 7.2
