#!/usr/bin/env python3
"""
End-to-end tests for all three services (electricity, gas, broadband)
"""

import pytest
from unittest.mock import Mock, patch
from pymercury.api import MercuryAPIClient
from pymercury.api.models import (
    ServiceUsage, ElectricityUsage, GasUsage, BroadbandUsage,
    ElectricityUsageContent, GasUsageContent
)


class TestAllServicesIntegration:
    """Test integration across all three services"""

    @pytest.fixture
    def mock_client(self):
        return MercuryAPIClient("dummy_token")

    def test_all_service_models_instantiate(self):
        """Test that all service models can be instantiated with realistic data"""

        # Test Electricity Usage
        electricity_data = {
            'serviceType': 'Electricity',
            'usagePeriod': 'Daily',
            'startDate': '2025-01-01T00:00:00+12:00',
            'endDate': '2025-01-10T00:00:00+12:00',
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 10.5, 'cost': 5.25},
                        {'date': '2025-01-02', 'consumption': 8.3, 'cost': 4.15}
                    ]
                }
            ],
            'averageTemperature': {
                'data': [{'temp': 18.5}, {'temp': 20.1}]
            }
        }

        electricity = ElectricityUsage(electricity_data)
        assert electricity.service_type == 'Electricity'
        assert electricity.total_usage == 18.8
        assert electricity.average_temperature == 19.3

        # Test Gas Usage
        gas_data = {
            'serviceType': 'Gas',
            'usagePeriod': 'Daily',
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {'date': '2025-01-01', 'consumption': 324.0, 'cost': 91.08},
                        {'date': '2025-01-02', 'consumption': 298.5, 'cost': 83.76}
                    ]
                }
            ]
        }

        gas = GasUsage(gas_data)
        assert gas.service_type == 'Gas'
        assert gas.total_usage == 622.5
        assert gas.average_temperature is None  # No temperature for gas

        # Test Broadband Usage
        broadband_data = {
            "avgDailyUsage": "15.75",
            "totalDataUsed": "315.0",
            "planName": "FibreMax Unlimited",
            "planCode": "30299",
            "dailyUsages": [
                {"date": "2025-01-01T00:00:00", "usage": "12.5"},
                {"date": "2025-01-02T00:00:00", "usage": "19.0"},
                {"date": "2025-01-03T00:00:00", "usage": "0.0"}
            ]
        }

        broadband = BroadbandUsage(broadband_data)
        assert broadband.service_type == "Broadband"
        assert broadband.plan_name == "FibreMax Unlimited"
        assert broadband.max_daily_usage == 19.0
        assert broadband.usage_days == 2  # Two non-zero days

    def test_inheritance_consistency(self):
        """Test that electricity and gas usage maintain consistent behavior through inheritance"""

        # Same base data for both services
        base_data = {
            'usagePeriod': 'Daily',
            'usage': [
                {
                    'label': 'actual',
                    'data': [
                        {'consumption': 100.0, 'cost': 50.0},
                        {'consumption': 200.0, 'cost': 100.0}
                    ]
                }
            ]
        }

        electricity_data = {**base_data, 'serviceType': 'Electricity'}
        gas_data = {**base_data, 'serviceType': 'Gas'}

        electricity = ElectricityUsage(electricity_data)
        gas = GasUsage(gas_data)

        # Both should calculate same statistics from same data
        assert electricity.total_usage == gas.total_usage == 300.0
        assert electricity.total_cost == gas.total_cost == 150.0
        assert electricity.max_daily_usage == gas.max_daily_usage == 200.0
        assert electricity.min_daily_usage == gas.min_daily_usage == 100.0
        assert electricity.data_points == gas.data_points == 2

    @patch.object(MercuryAPIClient, '_make_request')
    def test_all_service_content_methods(self, mock_request, mock_client):
        """Test content methods for electricity and gas"""

        # Test electricity content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': 'Electricity usage information',
            'title': 'Usage Info',
            'usageData': []
        }
        mock_request.return_value = mock_response

        electricity_content = mock_client.get_electricity_usage_content()
        assert isinstance(electricity_content, ElectricityUsageContent)

        # Test gas content
        mock_response.json.return_value = {
            'contentName': 'gas-usage',
            'locale': 'en-NZ',
            'content': {
                'disclaimer_usage': {'text': 'Gas usage disclaimer'},
                'usage_info_modal_title': {'text': 'Gas Usage Information'}
            }
        }

        gas_content = mock_client.get_gas_usage_content()
        assert isinstance(gas_content, GasUsageContent)
        assert gas_content.disclaimer_usage == 'Gas usage disclaimer'

    @patch.object(MercuryAPIClient, '_make_request')
    def test_all_usage_methods_with_intervals(self, mock_request, mock_client):
        """Test that all services support different intervals"""

        # Mock response for usage data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'serviceType': 'TestService',
            'usagePeriod': 'Hourly',
            'usage': [
                {
                    'label': 'actual',
                    'data': [{'consumption': 5.0, 'cost': 2.5}]
                }
            ]
        }
        mock_request.return_value = mock_response

        # Mock get_service_usage to return consistent data
        with patch.object(mock_client, 'get_service_usage') as mock_service_usage:
            mock_service_usage.return_value = ServiceUsage(mock_response.json.return_value)

            # Test electricity hourly and monthly
            electricity_hourly = mock_client.get_electricity_usage_hourly('123', '456', 'E789')
            electricity_monthly = mock_client.get_electricity_usage_monthly('123', '456', 'E789')

            assert isinstance(electricity_hourly, ElectricityUsage)
            assert isinstance(electricity_monthly, ElectricityUsage)

            # Test gas hourly and monthly
            gas_hourly = mock_client.get_gas_usage_hourly('123', '456', 'G789')
            gas_monthly = mock_client.get_gas_usage_monthly('123', '456', 'G789')

            assert isinstance(gas_hourly, GasUsage)
            assert isinstance(gas_monthly, GasUsage)

            # Verify service_usage was called appropriately
            assert mock_service_usage.call_count == 4

    def test_service_type_differentiation(self):
        """Test that different service types are properly differentiated"""

        # Create services with different types
        from pymercury.api.models.account import Service

        electricity_service = Service({
            'serviceId': 'E123',
            'serviceGroup': 'electricity',
            'serviceType': 'Electricity'
        })

        gas_service = Service({
            'serviceId': 'G456',
            'serviceGroup': 'gas',
            'serviceType': 'Gas'
        })

        broadband_service = Service({
            'serviceId': 'B789',
            'serviceGroup': 'broadband',
            'serviceType': 'Broadband'
        })

        # Test type identification
        assert electricity_service.is_electricity
        assert not electricity_service.is_gas
        assert not electricity_service.is_broadband

        assert gas_service.is_gas
        assert not gas_service.is_electricity
        assert not gas_service.is_broadband

        assert broadband_service.is_broadband
        assert not broadband_service.is_electricity
        assert not broadband_service.is_gas

    def test_mixed_service_portfolio(self):
        """Test handling a customer with all three service types"""

        from pymercury.api.models.account import Service, ServiceIds

        # Create a mixed portfolio
        services = [
            Service({'serviceId': 'E001', 'serviceGroup': 'electricity'}),
            Service({'serviceId': 'E002', 'serviceGroup': 'electricity'}),
            Service({'serviceId': 'G001', 'serviceGroup': 'gas'}),
            Service({'serviceId': 'B001', 'serviceGroup': 'broadband'}),
        ]

        service_ids = ServiceIds(services)

        # Verify proper categorization
        assert len(service_ids.all) == 4
        assert len(service_ids.electricity) == 2
        assert len(service_ids.gas) == 1
        assert len(service_ids.broadband) == 1

        assert 'E001' in service_ids.electricity
        assert 'E002' in service_ids.electricity
        assert 'G001' in service_ids.gas
        assert 'B001' in service_ids.broadband

    def test_error_handling_across_services(self, mock_client):
        """Test that error handling works consistently across all services"""

        with patch.object(mock_client, '_make_request') as mock_request:
            # Mock 404 error
            mock_response = Mock()
            mock_response.status_code = 404
            mock_request.return_value = mock_response

            # All service methods should handle errors gracefully
            assert mock_client.get_electricity_usage('123', '456', 'E789') is None
            assert mock_client.get_gas_usage('123', '456', 'G789') is None
            assert mock_client.get_broadband_usage('123', '456', 'B789') is None

    def test_verbose_logging(self):
        """Test that verbose logging works for all services"""

        # Create verbose client
        verbose_client = MercuryAPIClient("dummy_token", verbose=True)

        # Test that _log method exists and works
        assert hasattr(verbose_client, '_log')
        assert verbose_client.verbose is True

        # Should not raise any errors when called
        verbose_client._log("Test message")

    def test_api_method_naming_consistency(self, mock_client):
        """Test that API method naming is consistent across services"""

        # All services should have get_X_usage methods
        assert hasattr(mock_client, 'get_electricity_usage')
        assert hasattr(mock_client, 'get_gas_usage')
        assert hasattr(mock_client, 'get_broadband_usage')

        # Interval methods should follow same pattern
        assert hasattr(mock_client, 'get_electricity_usage_hourly')
        assert hasattr(mock_client, 'get_electricity_usage_monthly')
        assert hasattr(mock_client, 'get_gas_usage_hourly')
        assert hasattr(mock_client, 'get_gas_usage_monthly')

        # Content methods should follow same pattern
        assert hasattr(mock_client, 'get_electricity_usage_content')
        assert hasattr(mock_client, 'get_gas_usage_content')

        # Alias methods
        assert hasattr(mock_client, 'get_fibre_usage')  # Alias for broadband
