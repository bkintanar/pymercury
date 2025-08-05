#!/usr/bin/env python3
"""
Integration tests for MercuryAPIClient
"""

import pytest
from unittest.mock import Mock, patch
from pymercury.api import MercuryAPIClient
from pymercury.api.models import (
    CustomerInfo, Account, Service, ServiceIds, MeterInfo, BillSummary,
    ElectricityUsageContent, GasUsageContent, ServiceUsage,
    ElectricityUsage, GasUsage, BroadbandUsage
)
from pymercury.exceptions import MercuryAPIError, MercuryAPIConnectionError


class TestMercuryAPIClient:
    """Test MercuryAPIClient functionality"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock API client for testing"""
        return MercuryAPIClient("dummy_access_token", verbose=True)

    def test_client_initialization(self, mock_client):
        """Test client initialization"""
        assert mock_client.access_token == "dummy_access_token"
        assert mock_client.verbose is True
        assert mock_client.endpoints is not None
        assert mock_client.session is not None

    def test_build_headers(self, mock_client):
        """Test header building"""
        headers = mock_client._build_headers()

        assert 'Authorization' in headers
        assert headers['Authorization'] == 'Bearer dummy_access_token'
        assert headers['Content-Type'] == 'application/json'
        assert headers['Accept'] == 'application/json'
        assert 'User-Agent' in headers

    @patch('requests.Session.request')
    def test_successful_request(self, mock_request, mock_client):
        """Test successful API request"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'test': 'data'}
        mock_request.return_value = mock_response

        response = mock_client._make_request('GET', 'https://test.url')

        assert response.status_code == 200
        assert response.json() == {'test': 'data'}

    @patch('requests.Session.request')
    def test_401_error_handling(self, mock_request, mock_client):
        """Test 401 unauthorized error handling"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_request.return_value = mock_response

        with pytest.raises(Exception):  # Should raise MercuryAPIUnauthorizedError
            mock_client._make_request('GET', 'https://test.url')

    @patch('requests.Session.request')
    def test_404_error_handling(self, mock_request, mock_client):
        """Test 404 not found error handling"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        with pytest.raises(Exception):  # Should raise MercuryAPINotFoundError
            mock_client._make_request('GET', 'https://test.url')

    @patch('requests.Session.request')
    def test_connection_error(self, mock_request, mock_client):
        """Test connection error handling"""
        mock_request.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):  # Should raise MercuryAPIConnectionError
            mock_client._make_request('GET', 'https://test.url')


class TestAPIClientMethods:
    """Test specific API client methods"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock API client"""
        return MercuryAPIClient("dummy_token")

    @patch.object(MercuryAPIClient, '_make_request')
    def test_get_customer_info(self, mock_request, mock_client):
        """Test get_customer_info method"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'customerId': '123456',
            'name': 'John Smith',
            'email': 'john@example.com'
        }
        mock_request.return_value = mock_response

        result = mock_client.get_customer_info('123456')

        assert isinstance(result, CustomerInfo)
        assert result.customer_id == '123456'
        assert result.name == 'John Smith'
        assert result.email == 'john@example.com'

    @patch.object(MercuryAPIClient, '_make_request')
    def test_get_accounts(self, mock_request, mock_client):
        """Test get_accounts method"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'accountId': '111', 'accountName': 'Account 1'},
            {'accountId': '222', 'accountName': 'Account 2'}
        ]
        mock_request.return_value = mock_response

        result = mock_client.get_accounts('123456')

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(acc, Account) for acc in result)
        assert result[0].account_id == '111'
        assert result[1].account_id == '222'

    @patch.object(MercuryAPIClient, '_make_request')
    def test_get_services(self, mock_request, mock_client):
        """Test get_services method"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'services': [
                {
                    'serviceId': 'E123',
                    'serviceGroup': 'electricity',
                    'serviceType': 'Electricity'
                },
                {
                    'serviceId': 'G456',
                    'serviceGroup': 'gas',
                    'serviceType': 'Gas'
                }
            ]
        }
        mock_request.return_value = mock_response

        result = mock_client.get_services('123456', '789012')

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(svc, Service) for svc in result)
        assert result[0].service_id == 'E123'
        assert result[0].is_electricity
        assert result[1].service_id == 'G456'
        assert result[1].is_gas

    @patch.object(MercuryAPIClient, '_make_request')
    def test_get_broadband_usage(self, mock_request, mock_client):
        """Test get_broadband_usage method"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "avgDailyUsage": "8.55",
            "totalDataUsed": "42.73",
            "planName": "FibreClassic Unlimited Naked",
            "planCode": "20398",
            "dailyUsages": [
                {"date": "2025-08-01T00:00:00", "usage": "10.02"},
                {"date": "2025-08-02T00:00:00", "usage": "10.20"}
            ]
        }
        mock_request.return_value = mock_response

        result = mock_client.get_broadband_usage('123456', '789012', 'B123')

        assert isinstance(result, BroadbandUsage)
        assert result.plan_name == "FibreClassic Unlimited Naked"
        assert result.avg_daily_usage == 8.55
        assert result.total_data_used == 42.73
        assert len(result.daily_usages) == 2

    @patch.object(MercuryAPIClient, '_make_request')
    def test_get_electricity_usage(self, mock_request, mock_client):
        """Test get_electricity_usage method"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'serviceType': 'Electricity',
            'usagePeriod': 'Daily',
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 10.5, 'cost': 5.25}
                    ]
                }
            ]
        }
        mock_request.return_value = mock_response

        # Mock the get_service_usage method
        with patch.object(mock_client, 'get_service_usage') as mock_service_usage:
            mock_service_usage.return_value = ServiceUsage(mock_response.json.return_value)

            result = mock_client.get_electricity_usage('123', '456', 'E789')

            assert isinstance(result, ElectricityUsage)
            assert isinstance(result, ServiceUsage)  # Inheritance
            mock_service_usage.assert_called_once()

    @patch.object(MercuryAPIClient, '_make_request')
    def test_get_gas_usage(self, mock_request, mock_client):
        """Test get_gas_usage method"""
        mock_response = Mock()
        mock_response.status_code = 200
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
        mock_request.return_value = mock_response

        # Mock the get_service_usage method
        with patch.object(mock_client, 'get_service_usage') as mock_service_usage:
            mock_service_usage.return_value = ServiceUsage(mock_response.json.return_value)

            result = mock_client.get_gas_usage('123', '456', 'G789')

            assert isinstance(result, GasUsage)
            assert isinstance(result, ServiceUsage)  # Inheritance
            mock_service_usage.assert_called_once()

    def test_method_existence(self, mock_client):
        """Test that all expected methods exist on the client"""
        expected_methods = [
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
            'get_usage_content',
            'get_service_usage',
            'get_bill_summary',
            'get_electricity_meter_info',
            'get_electricity_plans',
            'get_electricity_meter_reads'
        ]

        for method_name in expected_methods:
            assert hasattr(mock_client, method_name), f"Method {method_name} missing"
            assert callable(getattr(mock_client, method_name)), f"Method {method_name} not callable"


class TestServiceIntegration:
    """Test integration between different services"""

    @pytest.fixture
    def mock_client(self):
        return MercuryAPIClient("dummy_token")

    def test_service_ids_integration(self, mock_client):
        """Test ServiceIds container with mixed services"""
        # Create mock services
        services = [
            Service({'serviceId': 'E123', 'serviceGroup': 'electricity'}),
            Service({'serviceId': 'G456', 'serviceGroup': 'gas'}),
            Service({'serviceId': 'B789', 'serviceGroup': 'broadband'}),
        ]

        service_ids = ServiceIds(services)

        assert len(service_ids.all) == 3
        assert 'E123' in service_ids.electricity
        assert 'G456' in service_ids.gas
        assert 'B789' in service_ids.broadband

    def test_alias_methods(self, mock_client):
        """Test that alias methods exist and work"""
        # Test fibre_usage is alias for broadband_usage
        assert hasattr(mock_client, 'get_fibre_usage')

        # Mock the broadband method
        with patch.object(mock_client, 'get_broadband_usage') as mock_broadband:
            mock_broadband.return_value = Mock()

            result = mock_client.get_fibre_usage('123', '456', 'B789')

            mock_broadband.assert_called_once_with('123', '456', 'B789')
