#!/usr/bin/env python3
"""
Integration tests for MercuryAPIClient
"""

import re
import pytest
import requests
from unittest.mock import Mock, patch
from urllib.parse import quote, unquote
from pymercury.api import MercuryAPIClient
from pymercury.api.models import (
    CustomerInfo, Account, Service, ServiceIds, MeterInfo, BillSummary,
    ElectricityUsageContent, GasUsageContent, ServiceUsage,
    ElectricityUsage, GasUsage, BroadbandUsage,
    ElectricitySummary, ElectricityPlans, ElectricityMeterReads,
)
from pymercury.exceptions import (
    MercuryAPIError,
    MercuryAPIConnectionError,
    MercuryAPIUnauthorizedError,
    MercuryAPINotFoundError,
    MercuryAPIRateLimitError,
)


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
        """Connection error must be wrapped as MercuryAPIConnectionError.

        The legacy version of this test used bare Exception, which never
        actually exercised the `except RequestException` branch — passes for
        the wrong reason. Fixed to use requests.exceptions.ConnectionError.
        """
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(MercuryAPIConnectionError):
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


# ===========================================================================
# Comprehensive coverage tests using requests-mock (the modern pattern).
# Replaces the old `@patch('requests.Session.request')` calls and exercises
# every code path in pymercury/api/client.py.
# ===========================================================================


@pytest.fixture
def api_client():
    return MercuryAPIClient("dummy_token", verbose=True)


@pytest.fixture
def base_api_url(api_client):
    return api_client.config.api_base_url.rstrip("/")


# ---- _make_request status-code mapping -------------------------------------


@pytest.mark.parametrize("status,expected_exc", [
    (401, MercuryAPIUnauthorizedError),
    (404, MercuryAPINotFoundError),
    (429, MercuryAPIRateLimitError),
    (500, MercuryAPIError),
    (403, MercuryAPIError),
    (400, MercuryAPIError),
])
def test_status_code_maps_to_specific_exception(
    requests_mock, api_client, base_api_url, status, expected_exc
):
    requests_mock.get(f"{base_api_url}/customers/c1", status_code=status, text="x")
    with pytest.raises(expected_exc):
        api_client.get_customer_info("c1")


# ---- close() / context manager ---------------------------------------------


def test_close_releases_session(api_client):
    api_client.close()
    # Calling again is safe.
    api_client.close()


def test_context_manager(api_client):
    with api_client as c:
        assert c is api_client


# ---- Specific methods using requests-mock ----------------------------------


def test_get_customer_info_happy(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1",
        json={"customerId": "c1", "name": "X", "email": "x@x.com"},
    )
    info = api_client.get_customer_info("c1")
    assert isinstance(info, CustomerInfo)
    assert info.customer_id == "c1"


def test_get_accounts_with_list_response(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts",
        json=[{"accountId": "a1"}, {"accountId": "a2"}],
    )
    accounts = api_client.get_accounts("c1")
    assert len(accounts) == 2


def test_get_accounts_with_single_object_response(requests_mock, api_client, base_api_url):
    """Tests the `[data] if data else []` branch — single dict wrapped to list."""
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts",
        json={"accountId": "solo"},
    )
    accounts = api_client.get_accounts("c1")
    assert len(accounts) == 1
    assert accounts[0].account_id == "solo"


def test_get_accounts_with_falsy_response(requests_mock, api_client, base_api_url):
    """Empty dict -> `[]`."""
    requests_mock.get(f"{base_api_url}/customers/c1/accounts", json={})
    accounts = api_client.get_accounts("c1")
    # {} is falsy in Python, so accounts_data = [] — no Account objects.
    assert accounts == []


def test_get_services_with_dict_services_key(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": [{"serviceId": "E1", "serviceGroup": "electricity"}]},
    )
    services = api_client.get_services("c1", "a1")
    assert len(services) == 1
    assert services[0].is_electricity


def test_get_services_with_list_response(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json=[{"serviceId": "G1", "serviceGroup": "gas"}],
    )
    services = api_client.get_services("c1", "a1")
    assert len(services) == 1
    assert services[0].is_gas


def test_get_services_with_unrecognized_shape(requests_mock, api_client, base_api_url):
    """The bare-else branch: services_data = []"""
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json="unexpected string",
    )
    services = api_client.get_services("c1", "a1")
    assert services == []


def test_get_services_include_all_true(requests_mock, api_client, base_api_url):
    """include_all=True drops the `?includeAll=false` query string."""
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services",
        json={"services": []},
    )
    services = api_client.get_services("c1", "a1", include_all=True)
    assert services == []


def test_get_all_services_iterates_accounts(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": [{"serviceId": "E1", "serviceGroup": "electricity"}]},
    )
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a2/services?includeAll=false",
        json={"services": [{"serviceId": "G1", "serviceGroup": "gas"}]},
    )
    services = api_client.get_all_services("c1", ["a1", "a2"])
    assert len(services) == 2


def test_get_service_ids(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": [
            {"serviceId": "E1", "serviceGroup": "electricity"},
            {"serviceId": "G1", "serviceGroup": "gas"},
        ]},
    )
    ids = api_client.get_service_ids("c1", ["a1"])
    assert ids.electricity == ["E1"]
    assert ids.gas == ["G1"]


def test_get_electricity_meter_info(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/electricity/meter-info",
        json={"meterservices": [{"serviceId": "svc-1", "smartMeterCommunicating": True}]},
    )
    info = api_client.get_electricity_meter_info("c1", "a1")
    assert isinstance(info, MeterInfo)
    assert info.service_id == "svc-1"


def test_get_bill_summary(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/bill-summary",
        json={"balance": 100.0},
    )
    bs = api_client.get_bill_summary("c1", "a1")
    assert isinstance(bs, BillSummary)
    assert bs.current_balance == 100.0


def test_get_electricity_usage_content(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/content/my-account?path=Electricity%2FUsage",
        json={"title": "Electricity"},
    )
    c = api_client.get_electricity_usage_content()
    assert isinstance(c, ElectricityUsageContent)


def test_get_gas_usage_content(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/content/my-account?path=Gas%2FUsage",
        json={"contentName": "Gas"},
    )
    c = api_client.get_gas_usage_content()
    assert isinstance(c, GasUsageContent)


def test_get_usage_content_returns_raw_dict(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/content/my-account?path=Solar%2FUsage",
        json={"foo": "bar"},
    )
    result = api_client.get_usage_content("Solar")
    assert result == {"foo": "bar"}


def test_get_service_usage_with_default_dates(requests_mock, api_client, base_api_url):
    """Exercises the end_date=None and start_date=None default branches."""
    # Mercury's URL includes encoded dates — match any URL on the right path.
    requests_mock.get(
        re.compile(r".*"),
        json={
            "serviceType": "electricity",
            "usagePeriod": "Daily",
            "usage": [{"label": "actual", "data": []}],
        },
    )
    result = api_client.get_service_usage("c1", "a1", "electricity", "svc-1")
    assert isinstance(result, ServiceUsage)


def test_get_service_usage_with_explicit_dates(requests_mock, api_client, base_api_url):
    """Exercises the parse-end_date branch (end_dt is None initially)."""
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Daily", "usage": []},
    )
    result = api_client.get_service_usage(
        "c1", "a1", "electricity", "svc-1",
        start_date=quote("2026-04-01T00:00:00+12:00"),
        end_date=quote("2026-04-15T00:00:00+12:00"),
    )
    assert isinstance(result, ServiceUsage)


def test_get_service_usage_falls_back_on_bad_end_date(requests_mock, api_client):
    """If end_date can't be parsed, fallback datetime is used and the URL still resolves."""
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "x", "usagePeriod": "Daily", "usage": []},
    )
    # Provide an invalid end_date string so fromisoformat raises -> fallback path.
    result = api_client.get_service_usage(
        "c1", "a1", "electricity", "svc-1",
        end_date="not-a-date",
    )
    assert isinstance(result, ServiceUsage)


def test_get_gas_usage_returns_none_when_underlying_returns_none(api_client):
    """When get_service_usage returns None, get_gas_usage returns None."""
    with patch.object(api_client, "get_service_usage", return_value=None):
        assert api_client.get_gas_usage("c1", "a1", "g1") is None


def test_get_electricity_summary_with_default_date(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "Electricity", "weeklySummary": {"usage": []}},
    )
    result = api_client.get_electricity_summary("c1", "a1", "svc-1")
    assert isinstance(result, ElectricitySummary)


def test_get_electricity_summary_with_explicit_date(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "Electricity", "weeklySummary": {"usage": []}},
    )
    result = api_client.get_electricity_summary(
        "c1", "a1", "svc-1", as_of_date=quote("2026-04-26T00:00:00+12:00")
    )
    assert isinstance(result, ElectricitySummary)


def test_get_electricity_usage_returns_none_when_underlying_none(api_client):
    with patch.object(api_client, "get_service_usage", return_value=None):
        assert api_client.get_electricity_usage("c1", "a1", "svc-1") is None


def test_get_electricity_usage_hourly_default_dates(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Hourly", "usage": []},
    )
    result = api_client.get_electricity_usage_hourly("c1", "a1", "svc-1")
    assert isinstance(result, ElectricityUsage)


def test_get_electricity_usage_hourly_explicit_end_date(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Hourly", "usage": []},
    )
    result = api_client.get_electricity_usage_hourly(
        "c1", "a1", "svc-1",
        end_date=quote("2026-04-15T00:00:00+12:00"),
    )
    assert isinstance(result, ElectricityUsage)


def test_get_electricity_usage_hourly_fallback_on_bad_date(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Hourly", "usage": []},
    )
    result = api_client.get_electricity_usage_hourly(
        "c1", "a1", "svc-1", end_date="garbage"
    )
    assert isinstance(result, ElectricityUsage)


def test_get_electricity_usage_monthly_default_dates(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Monthly", "usage": []},
    )
    result = api_client.get_electricity_usage_monthly("c1", "a1", "svc-1")
    assert isinstance(result, ElectricityUsage)


def test_get_electricity_usage_monthly_explicit_end_date(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Monthly", "usage": []},
    )
    result = api_client.get_electricity_usage_monthly(
        "c1", "a1", "svc-1",
        end_date=quote("2026-04-15T00:00:00+12:00"),
    )
    assert isinstance(result, ElectricityUsage)


def test_get_electricity_usage_monthly_fallback_on_bad_date(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Monthly", "usage": []},
    )
    result = api_client.get_electricity_usage_monthly(
        "c1", "a1", "svc-1", end_date="garbage"
    )
    assert isinstance(result, ElectricityUsage)


def test_get_gas_usage_hourly_delegates(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "gas", "usagePeriod": "Hourly", "usage": []},
    )
    result = api_client.get_gas_usage_hourly("c1", "a1", "g1")
    assert isinstance(result, GasUsage)


def test_get_gas_usage_monthly_delegates(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "gas", "usagePeriod": "Monthly", "usage": []},
    )
    result = api_client.get_gas_usage_monthly("c1", "a1", "g1")
    assert isinstance(result, GasUsage)


def test_get_broadband_usage(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/fibre/b1",
        json={"planName": "P", "avgDailyUsage": "1.0", "totalDataUsed": "10.0"},
    )
    result = api_client.get_broadband_usage("c1", "a1", "b1")
    assert isinstance(result, BroadbandUsage)


def test_get_electricity_plans_happy(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": [{
            "serviceId": "svc-1",
            "serviceGroup": "electricity",
            "identifier": "ICP-1",
        }]},
    )
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/electricity/svc-1/ICP-1/plans",
        json={"canChangePlan": True, "currentPlan": {"planId": "p1"}},
    )
    plans = api_client.get_electricity_plans("c1", "a1", "svc-1")
    assert isinstance(plans, ElectricityPlans)
    assert plans.icp_number == "ICP-1"


def test_get_electricity_plans_returns_none_when_no_icp(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": [{
            "serviceId": "svc-1",
            "serviceGroup": "electricity",
            # No identifier => no ICP
        }]},
    )
    assert api_client.get_electricity_plans("c1", "a1", "svc-1") is None


def test_get_electricity_plans_returns_none_when_no_services(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": []},
    )
    assert api_client.get_electricity_plans("c1", "a1", "svc-1") is None


def test_get_electricity_meter_reads_with_dict_response(requests_mock, api_client, base_api_url):
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/electricity/svc-1/meter-reads",
        json={"meterReads": [{"registers": [{"lastReading": "100"}]}]},
    )
    reads = api_client.get_electricity_meter_reads("c1", "a1", "svc-1")
    assert isinstance(reads, ElectricityMeterReads)


def test_get_electricity_meter_reads_with_list_response(requests_mock, api_client, base_api_url):
    """Exercises the `if isinstance(data, list): data = {'meterReads': data}` branch."""
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/electricity/svc-1/meter-reads",
        json=[{"registers": [{"lastReading": "200"}]}],
    )
    reads = api_client.get_electricity_meter_reads("c1", "a1", "svc-1")
    assert isinstance(reads, ElectricityMeterReads)


def test_get_electricity_meter_reads_with_unexpected_type(requests_mock, api_client, base_api_url):
    """Exercises the `elif not isinstance(data, dict): return None` branch."""
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/electricity/svc-1/meter-reads",
        json="unexpected string",
    )
    assert api_client.get_electricity_meter_reads("c1", "a1", "svc-1") is None


def test_get_electricity_usage_hourly_both_dates_provided(requests_mock, api_client):
    """Exercises the branch where start_date is supplied (the inner if is skipped)."""
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Hourly", "usage": []},
    )
    result = api_client.get_electricity_usage_hourly(
        "c1", "a1", "svc-1",
        start_date=quote("2026-04-13T00:00:00+12:00"),
        end_date=quote("2026-04-15T00:00:00+12:00"),
    )
    assert isinstance(result, ElectricityUsage)


def test_get_electricity_usage_monthly_both_dates_provided(requests_mock, api_client):
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Monthly", "usage": []},
    )
    result = api_client.get_electricity_usage_monthly(
        "c1", "a1", "svc-1",
        start_date=quote("2025-04-26T00:00:00+12:00"),
        end_date=quote("2026-04-26T00:00:00+12:00"),
    )
    assert isinstance(result, ElectricityUsage)


def test_get_service_usage_with_explicit_start_date_only(requests_mock, api_client):
    """Exercises the start_date provided / end_date None branch."""
    requests_mock.get(
        re.compile(r".*"),
        json={"serviceType": "electricity", "usagePeriod": "Daily", "usage": []},
    )
    result = api_client.get_service_usage(
        "c1", "a1", "electricity", "svc-1",
        start_date=quote("2026-04-01T00:00:00+12:00"),
    )
    assert isinstance(result, ServiceUsage)


def test_get_electricity_plans_skips_non_matching_service_first(
    requests_mock, api_client, base_api_url
):
    """For-loop iterates past a service that doesn't match before finding the
    target — exercises the continue path (777->776)."""
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services?includeAll=false",
        json={"services": [
            {"serviceId": "other-svc", "serviceGroup": "gas"},  # doesn't match
            {
                "serviceId": "svc-1",
                "serviceGroup": "electricity",
                "identifier": "ICP-1",
            },
        ]},
    )
    requests_mock.get(
        f"{base_api_url}/customers/c1/accounts/a1/services/electricity/svc-1/ICP-1/plans",
        json={"canChangePlan": True},
    )
    plans = api_client.get_electricity_plans("c1", "a1", "svc-1")
    assert isinstance(plans, ElectricityPlans)
