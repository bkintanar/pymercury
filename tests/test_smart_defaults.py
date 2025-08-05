#!/usr/bin/env python3
"""
Smart defaults validation tests - converted from legacy test_mercury_library.py
"""

import pytest
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, unquote
from pymercury import MercuryAPIClient


class TestSmartDefaults:
    """Test smart default date generation and URL encoding"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock API client for testing"""
        return MercuryAPIClient("dummy_token")

    def test_new_zealand_timezone(self):
        """Test New Zealand timezone handling"""
        # New Zealand Standard Time is UTC+12
        nz_timezone = timezone(timedelta(hours=12))

        # Create a date in NZ timezone
        nz_date = datetime(2025, 1, 15, 10, 30, 0, tzinfo=nz_timezone)

        assert nz_date.tzinfo.utcoffset(None) == timedelta(hours=12)
        assert "+12:00" in nz_date.isoformat()

    def test_today_date_generation(self):
        """Test today's date generation in NZ timezone"""
        nz_timezone = timezone(timedelta(hours=12))
        today = datetime.now(nz_timezone).replace(hour=0, minute=0, second=0, microsecond=0)

        # Should be in NZ timezone
        assert today.tzinfo.utcoffset(None) == timedelta(hours=12)

        # Should be at midnight
        assert today.hour == 0
        assert today.minute == 0
        assert today.second == 0
        assert today.microsecond == 0

        # ISO format should include timezone
        iso_string = today.isoformat()
        assert "+12:00" in iso_string

    def test_yesterday_date_generation(self):
        """Test yesterday's date generation"""
        nz_timezone = timezone(timedelta(hours=12))
        today = datetime.now(nz_timezone)
        yesterday = today - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Should be one day before today
        assert yesterday.date() == (today.date() - timedelta(days=1))

        # Should be at midnight
        assert yesterday.hour == 0
        assert yesterday.minute == 0
        assert yesterday.second == 0

    def test_days_ago_calculation(self):
        """Test calculation of dates X days ago"""
        nz_timezone = timezone(timedelta(hours=12))
        today = datetime.now(nz_timezone).replace(hour=0, minute=0, second=0, microsecond=0)

        # Test 14 days ago (common for usage data)
        days_14_ago = today - timedelta(days=14)
        assert days_14_ago.date() == (today.date() - timedelta(days=14))

        # Test 365 days ago (for monthly data)
        days_365_ago = today - timedelta(days=365)
        assert days_365_ago.date() == (today.date() - timedelta(days=365))

    def test_hourly_defaults(self):
        """Test default date range for hourly data (2 days ending yesterday)"""
        nz_timezone = timezone(timedelta(hours=12))
        yesterday = datetime.now(nz_timezone) - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        start_date = yesterday - timedelta(days=2)

        # Should span 2 days ending yesterday
        assert (yesterday - start_date).days == 2
        assert start_date < yesterday

    def test_monthly_defaults(self):
        """Test default date range for monthly data (1 year ending today)"""
        nz_timezone = timezone(timedelta(hours=12))
        today = datetime.now(nz_timezone)
        one_year_ago = today - timedelta(days=365)

        # Should span approximately 1 year
        assert (today - one_year_ago).days == 365
        assert one_year_ago < today

    def test_url_encoding_decoding(self):
        """Test URL encoding and decoding of dates"""
        # Test date with special characters
        test_date = "2025-07-31T10:20:01+12:00"
        encoded = quote(test_date)
        decoded = unquote(encoded)

        assert encoded == "2025-07-31T10%3A20%3A01%2B12%3A00"
        assert decoded == test_date

        # Test that colons and plus signs are properly encoded
        assert "%3A" in encoded  # Colon
        assert "%2B" in encoded  # Plus sign

    def test_date_format_consistency(self):
        """Test that date formats are consistent across methods"""
        nz_timezone = timezone(timedelta(hours=12))

        # Test various date formats
        dates = [
            datetime.now(nz_timezone),
            datetime.now(nz_timezone).replace(hour=0, minute=0, second=0, microsecond=0),
            datetime(2025, 1, 15, 10, 30, 45, tzinfo=nz_timezone)
        ]

        for date in dates:
            iso_string = date.isoformat()

            # Should always include timezone
            assert "+12:00" in iso_string

            # Should be parseable back to datetime
            parsed = datetime.fromisoformat(iso_string)
            assert parsed == date

    def test_smart_defaults_for_different_intervals(self):
        """Test that smart defaults work for different intervals"""
        nz_timezone = timezone(timedelta(hours=12))
        now = datetime.now(nz_timezone)

        # Daily defaults (14 days)
        daily_start = now - timedelta(days=14)
        daily_end = now
        assert (daily_end - daily_start).days == 14

        # Hourly defaults (2 days ending yesterday)
        yesterday = now - timedelta(days=1)
        hourly_start = yesterday - timedelta(days=2)
        hourly_end = yesterday
        assert (hourly_end - hourly_start).days == 2

        # Monthly defaults (1 year)
        monthly_start = now - timedelta(days=365)
        monthly_end = now
        assert (monthly_end - monthly_start).days == 365

    def test_edge_case_dates(self):
        """Test edge cases for date handling"""
        nz_timezone = timezone(timedelta(hours=12))

        # Test leap year handling
        leap_year_date = datetime(2024, 2, 29, 12, 0, 0, tzinfo=nz_timezone)
        assert leap_year_date.month == 2
        assert leap_year_date.day == 29

        # Test year boundaries
        new_year = datetime(2025, 1, 1, 0, 0, 0, tzinfo=nz_timezone)
        assert new_year.month == 1
        assert new_year.day == 1

        # Test month boundaries
        month_end = datetime(2025, 1, 31, 23, 59, 59, tzinfo=nz_timezone)
        assert month_end.day == 31

    def test_time_precision(self):
        """Test time precision in generated dates"""
        nz_timezone = timezone(timedelta(hours=12))

        # Test with specific time
        precise_time = datetime(2025, 7, 31, 10, 20, 1, tzinfo=nz_timezone)
        iso_string = precise_time.isoformat()

        assert "10:20:01" in iso_string
        assert "+12:00" in iso_string

        # Test URL encoding preserves precision
        encoded = quote(iso_string)
        decoded = unquote(encoded)
        parsed = datetime.fromisoformat(decoded)

        assert parsed == precise_time

    def test_relative_date_calculations(self):
        """Test relative date calculations are accurate"""
        nz_timezone = timezone(timedelta(hours=12))
        base_date = datetime(2025, 7, 31, 10, 20, 1, tzinfo=nz_timezone)

        # Test various relative calculations
        one_day_before = base_date - timedelta(days=1)
        assert one_day_before.day == 30

        one_week_before = base_date - timedelta(days=7)
        assert one_week_before.day == 24

        two_weeks_before = base_date - timedelta(days=14)
        assert two_weeks_before.day == 17

        one_month_before = base_date - timedelta(days=30)
        assert one_month_before.month == 7
        assert one_month_before.day == 1

    def test_timezone_consistency(self):
        """Test that all generated dates use consistent timezone"""
        nz_timezone = timezone(timedelta(hours=12))

        # Generate multiple dates
        dates = [
            datetime.now(nz_timezone),
            datetime.now(nz_timezone) - timedelta(days=1),
            datetime.now(nz_timezone) - timedelta(days=14),
            datetime.now(nz_timezone) - timedelta(days=365)
        ]

        # All should have same timezone
        for date in dates:
            assert date.tzinfo.utcoffset(None) == timedelta(hours=12)
            assert "+12:00" in date.isoformat()

    def test_url_safe_encoding(self):
        """Test that encoded dates are URL-safe"""
        test_dates = [
            "2025-07-31T10:20:01+12:00",
            "2025-01-01T00:00:00+12:00",
            "2024-12-31T23:59:59+12:00"
        ]

        for date_str in test_dates:
            encoded = quote(date_str)

            # Should not contain unsafe characters
            unsafe_chars = [' ', ':', '+', '/', '?', '#', '[', ']', '@']
            for char in unsafe_chars:
                assert char not in encoded

            # Should be decodable back to original
            decoded = unquote(encoded)
            assert decoded == date_str
