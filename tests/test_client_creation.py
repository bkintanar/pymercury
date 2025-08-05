#!/usr/bin/env python3
"""
Client creation tests - converted from legacy test_mercury_library.py
"""

import pytest
from pymercury import MercuryClient, MercuryOAuthClient, MercuryAPIClient, MercuryConfig


class TestClientCreation:
    """Test all client classes can be created correctly"""

    def test_mercury_client_creation(self):
        """Test MercuryClient can be created"""
        client = MercuryClient("test@example.com", "password")

        assert client is not None
        # Email is None until login() is called
        assert client.email is None
        assert client._email == "test@example.com"
        assert client._password == "password"
        assert hasattr(client, 'login')
        assert hasattr(client, 'get_complete_account_data')

    def test_mercury_oauth_client_creation(self):
        """Test MercuryOAuthClient can be created"""
        oauth_client = MercuryOAuthClient("test@example.com", "password")

        assert oauth_client is not None
        assert oauth_client.email == "test@example.com"
        assert oauth_client.password == "password"
        assert hasattr(oauth_client, 'authenticate')
        assert hasattr(oauth_client, 'login_or_refresh')

    def test_mercury_api_client_creation(self):
        """Test MercuryAPIClient can be created"""
        api_client = MercuryAPIClient("dummy_token")

        assert api_client is not None
        assert api_client.access_token == "dummy_token"
        assert hasattr(api_client, 'get_customer_info')
        assert hasattr(api_client, 'get_accounts')
        assert hasattr(api_client, 'get_services')
        assert hasattr(api_client, 'get_electricity_usage')
        assert hasattr(api_client, 'get_gas_usage')
        assert hasattr(api_client, 'get_broadband_usage')

    def test_custom_configuration(self):
        """Test clients can be created with custom configuration"""
        config = MercuryConfig(timeout=60, user_agent="TestApp/1.0")

        # Test with MercuryClient
        client = MercuryClient("test@example.com", "password", config=config)
        assert client.config.timeout == 60
        assert client.config.user_agent == "TestApp/1.0"

        # Test with MercuryOAuthClient
        oauth_client = MercuryOAuthClient("test@example.com", "password", config=config)
        assert oauth_client.config.timeout == 60
        assert oauth_client.config.user_agent == "TestApp/1.0"

        # Test with MercuryAPIClient
        api_client = MercuryAPIClient("dummy_token", config=config)
        assert api_client.config.timeout == 60
        assert api_client.config.user_agent == "TestApp/1.0"

    def test_verbose_mode(self):
        """Test clients can be created in verbose mode"""
        # Test API client with verbose mode
        api_client = MercuryAPIClient("dummy_token", verbose=True)
        assert api_client.verbose is True
        assert hasattr(api_client, '_log')

        # Test that _log method works
        api_client._log("Test message")  # Should not raise error

    def test_default_configuration(self):
        """Test clients use default configuration when none provided"""
        from pymercury.config import default_config

        client = MercuryAPIClient("dummy_token")

        # Should use default config
        assert client.config.api_base_url == default_config.api_base_url
        assert client.config.timeout == default_config.timeout
        assert client.config.max_redirects == default_config.max_redirects

    def test_client_initialization_parameters(self):
        """Test that clients properly initialize with all parameters"""
        config = MercuryConfig(
            timeout=120,
            max_redirects=10,
            user_agent="CustomAgent/2.0"
        )

        # Test API client with all parameters
        api_client = MercuryAPIClient(
            access_token="test_token_123",
            config=config,
            verbose=True
        )

        assert api_client.access_token == "test_token_123"
        assert api_client.config.timeout == 120
        assert api_client.config.max_redirects == 10
        assert api_client.config.user_agent == "CustomAgent/2.0"
        assert api_client.verbose is True

    def test_client_methods_available(self):
        """Test that all expected methods are available on clients"""
        # Test MercuryClient methods
        client = MercuryClient("test@example.com", "password")
        expected_mercury_methods = [
            'login',
            'get_complete_account_data'
        ]

        for method in expected_mercury_methods:
            assert hasattr(client, method), f"MercuryClient missing method: {method}"
            assert callable(getattr(client, method)), f"MercuryClient method not callable: {method}"

        # Test MercuryOAuthClient methods
        oauth_client = MercuryOAuthClient("test@example.com", "password")
        expected_oauth_methods = [
            'authenticate',
            'login_or_refresh',
            'refresh_tokens'
        ]

        for method in expected_oauth_methods:
            assert hasattr(oauth_client, method), f"MercuryOAuthClient missing method: {method}"
            assert callable(getattr(oauth_client, method)), f"MercuryOAuthClient method not callable: {method}"

        # Test MercuryAPIClient methods (comprehensive list)
        api_client = MercuryAPIClient("dummy_token")
        expected_api_methods = [
            'get_customer_info',
            'get_accounts',
            'get_services',
            'get_electricity_usage',
            'get_electricity_usage_hourly',
            'get_electricity_usage_monthly',
            'get_gas_usage',
            'get_gas_usage_hourly',
            'get_gas_usage_monthly',
            'get_broadband_usage',
            'get_fibre_usage',
            'get_electricity_usage_content',
            'get_gas_usage_content',
            'get_bill_summary',
            'get_electricity_meter_info',
            'get_electricity_plans',
            'get_electricity_meter_reads'
        ]

        for method in expected_api_methods:
            assert hasattr(api_client, method), f"MercuryAPIClient missing method: {method}"
            assert callable(getattr(api_client, method)), f"MercuryAPIClient method not callable: {method}"

    def test_client_session_initialization(self):
        """Test that API client properly initializes session"""
        api_client = MercuryAPIClient("test_token")

        # Should have session
        assert hasattr(api_client, 'session')
        assert api_client.session is not None

        # Session should have proper headers
        headers = api_client.session.headers
        assert 'Authorization' in headers
        assert 'Bearer test_token' in headers['Authorization']
        assert headers['Content-Type'] == 'application/json'
        assert headers['Accept'] == 'application/json'

    def test_endpoints_initialization(self):
        """Test that API client properly initializes endpoints"""
        api_client = MercuryAPIClient("test_token")

        # Should have endpoints
        assert hasattr(api_client, 'endpoints')
        assert api_client.endpoints is not None

        # Endpoints should have expected methods
        expected_endpoint_methods = [
            'customer_info',
            'customer_accounts',
            'account_services',
            'electricity_usage',
            'gas_usage',
            'broadband_service_info'
        ]

        for method in expected_endpoint_methods:
            assert hasattr(api_client.endpoints, method), f"Endpoints missing method: {method}"
