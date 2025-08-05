#!/usr/bin/env python3
"""
Endpoint URL generation tests - converted from legacy test_mercury_library.py
"""

import pytest
from pymercury.api.endpoints import MercuryAPIEndpoints


class TestEndpoints:
    """Test endpoint URL generation"""

    @pytest.fixture
    def endpoints(self):
        """Create endpoints instance for testing"""
        return MercuryAPIEndpoints("https://apis.mercury.co.nz/selfservice/v1")

    def test_customer_info_endpoint(self, endpoints):
        """Test customer info endpoint generation"""
        url = endpoints.customer_info("123456")

        assert "https://apis.mercury.co.nz/selfservice/v1" in url
        assert "customers/123456" in url
        assert url.startswith("https://")

    def test_customer_accounts_endpoint(self, endpoints):
        """Test customer accounts endpoint generation"""
        url = endpoints.customer_accounts("123456")

        assert "customers/123456/accounts" in url
        assert url.startswith("https://")

    def test_account_services_endpoint(self, endpoints):
        """Test account services endpoint generation"""
        url = endpoints.account_services("123456", "789012")

        assert "customers/123456/accounts/789012/services" in url
        assert url.startswith("https://")

    def test_account_services_with_include_all(self, endpoints):
        """Test account services endpoint with include_all parameter"""
        url = endpoints.account_services("123456", "789012", include_all=True)

        assert "customers/123456/accounts/789012/services" in url
        # When include_all=True, no query parameter is added (default behavior)
        assert url.endswith("/services")
        assert url.startswith("https://")

    def test_electricity_meter_info_endpoint(self, endpoints):
        """Test electricity meter info endpoint generation"""
        url = endpoints.electricity_meter_info("123456", "789012")

        assert "customers/123456/accounts/789012/services/electricity/meter-info" in url
        assert url.startswith("https://")

    def test_bill_summary_endpoint(self, endpoints):
        """Test bill summary endpoint generation"""
        url = endpoints.bill_summary("123456", "789012")

        assert "customers/123456/accounts/789012/bill-summary" in url
        assert url.startswith("https://")

    def test_electricity_usage_content_endpoint(self, endpoints):
        """Test electricity usage content endpoint generation"""
        url = endpoints.electricity_usage_content()

        assert "content/my-account" in url
        assert "Electricity%2FUsage" in url
        assert url.startswith("https://")

    def test_gas_usage_content_endpoint(self, endpoints):
        """Test gas usage content endpoint generation"""
        url = endpoints.gas_usage_content()

        assert "content/my-account" in url
        assert "Gas%2FUsage" in url
        assert url.startswith("https://")

    def test_generic_usage_content_endpoint(self, endpoints):
        """Test generic usage content endpoint generation"""
        url = endpoints.usage_content("Electricity")

        assert "content/my-account" in url
        assert "Electricity%2FUsage" in url
        assert url.startswith("https://")

        # Test with Gas
        url = endpoints.usage_content("Gas")
        assert "Gas%2FUsage" in url

    def test_electricity_summary_endpoint(self, endpoints):
        """Test electricity summary endpoint generation"""
        url = endpoints.electricity_summary("123456", "789012", "E001", "2025-01-01T00:00:00+12:00")

        assert "customers/123456/accounts/789012/services/electricity/E001/summary" in url
        assert "asOfDate=2025-01-01T00:00:00+12:00" in url
        assert url.startswith("https://")

    def test_electricity_usage_endpoint(self, endpoints):
        """Test electricity usage endpoint generation"""
        url = endpoints.electricity_usage(
            "123456", "789012", "E001", "daily",
            "2025-01-01T00:00:00+12:00", "2025-01-10T00:00:00+12:00"
        )

        assert "customers/123456/accounts/789012/services/electricity/E001/usage" in url
        assert "interval=daily" in url
        assert "startDate=2025-01-01T00:00:00+12:00" in url
        assert "endDate=2025-01-10T00:00:00+12:00" in url
        assert url.startswith("https://")

    def test_gas_usage_endpoint(self, endpoints):
        """Test gas usage endpoint generation"""
        url = endpoints.gas_usage(
            "123456", "789012", "G001", "daily",
            "2025-01-01T00:00:00+12:00", "2025-01-10T00:00:00+12:00"
        )

        assert "customers/123456/accounts/789012/services/gas/G001/usage" in url
        assert "interval=daily" in url
        assert "startDate=2025-01-01T00:00:00+12:00" in url
        assert "endDate=2025-01-10T00:00:00+12:00" in url
        assert url.startswith("https://")

    def test_generic_service_usage_endpoint(self, endpoints):
        """Test generic service usage endpoint generation"""
        url = endpoints.service_usage(
            "123456", "789012", "electricity", "E001", "hourly",
            "2025-01-01T00:00:00+12:00", "2025-01-10T00:00:00+12:00"
        )

        assert "customers/123456/accounts/789012/services/electricity/E001/usage" in url
        assert "interval=hourly" in url
        assert url.startswith("https://")

        # Test with gas
        url = endpoints.service_usage(
            "123456", "789012", "gas", "G001", "monthly",
            "2024-01-01T00:00:00+12:00", "2025-01-01T00:00:00+12:00"
        )

        assert "services/gas/G001/usage" in url
        assert "interval=monthly" in url

    def test_broadband_service_info_endpoint(self, endpoints):
        """Test broadband service info endpoint generation"""
        url = endpoints.broadband_service_info("123456", "789012", "B001")

        assert "customers/123456/accounts/789012/services/fibre/B001" in url
        assert url.startswith("https://")

    def test_fibre_service_info_endpoint(self, endpoints):
        """Test fibre service info endpoint generation (alias)"""
        url = endpoints.fibre_service_info("123456", "789012", "B001")

        assert "customers/123456/accounts/789012/services/fibre/B001" in url
        assert url.startswith("https://")

        # Should be same as broadband_service_info
        broadband_url = endpoints.broadband_service_info("123456", "789012", "B001")
        assert url == broadband_url

    def test_electricity_plans_endpoint(self, endpoints):
        """Test electricity plans endpoint generation"""
        url = endpoints.electricity_plans("123456", "789012", "E001", "0001234567UN001")

        assert "customers/123456/accounts/789012/services/electricity/E001/0001234567UN001/plans" in url
        assert url.startswith("https://")

    def test_electricity_meter_reads_endpoint(self, endpoints):
        """Test electricity meter reads endpoint generation"""
        url = endpoints.electricity_meter_reads("123456", "789012", "E001")

        assert "customers/123456/accounts/789012/services/electricity/E001/meter-reads" in url
        assert url.startswith("https://")

    def test_base_url_configuration(self):
        """Test that endpoints work with different base URLs"""
        custom_base = "https://test.api.mercury.co.nz/v2"
        endpoints = MercuryAPIEndpoints(custom_base)

        url = endpoints.customer_info("123456")

        assert url.startswith(custom_base)
        assert "customers/123456" in url

    def test_url_encoding(self, endpoints):
        """Test that URL parameters are properly encoded"""
        # Test with URL-encoded date
        encoded_date = "2025-01-01T10%3A20%3A01%2B12%3A00"
        url = endpoints.electricity_summary("123456", "789012", "E001", encoded_date)

        assert f"asOfDate={encoded_date}" in url

    def test_endpoint_parameter_validation(self, endpoints):
        """Test endpoint behavior with various parameter types"""
        # Test with string parameters
        url = endpoints.customer_info("123456")
        assert "customers/123456" in url

        # Test with different customer ID formats
        url = endpoints.customer_info("7334151")
        assert "customers/7334151" in url

        # Test with different account ID formats
        url = endpoints.customer_accounts("7334151")
        assert "customers/7334151/accounts" in url

    def test_all_endpoints_return_strings(self, endpoints):
        """Test that all endpoint methods return valid URL strings"""
        # Test methods that don't require parameters
        simple_endpoints = [
            endpoints.electricity_usage_content(),
            endpoints.gas_usage_content(),
        ]

        for url in simple_endpoints:
            assert isinstance(url, str)
            assert len(url) > 0
            assert url.startswith("https://")

        # Test methods that require parameters
        endpoints_with_account = [
            endpoints.account_services("123456", "789012"),
            endpoints.bill_summary("123456", "789012"),
            endpoints.broadband_service_info("123456", "789012", "B001")
        ]

        endpoints_customer_only = [
            endpoints.customer_accounts("123456"),
        ]

        # Test endpoints that include account ID
        for url in endpoints_with_account:
            assert isinstance(url, str)
            assert len(url) > 0
            assert url.startswith("https://")
            assert "123456" in url
            assert "789012" in url

        # Test endpoints that only include customer ID
        for url in endpoints_customer_only:
            assert isinstance(url, str)
            assert len(url) > 0
            assert url.startswith("https://")
            assert "123456" in url
