#!/usr/bin/env python3
"""
Mercury.co.nz API Client

Client for interacting with Mercury.co.nz selfservice API.
"""

import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, unquote

from ..config import MercuryConfig, default_config
from ..exceptions import (
    MercuryAPIError,
    MercuryAPIConnectionError,
    MercuryAPIUnauthorizedError,
    MercuryAPINotFoundError,
    MercuryAPIRateLimitError
)
from .endpoints import MercuryAPIEndpoints

# Import all models from the models package
from .models import (
    # Base
    ServiceUsage,

    # Account management
    CustomerInfo,
    Account,
    Service,
    ServiceIds,

    # Billing and meter
    MeterInfo,
    BillSummary,

    # Electricity
    ElectricityUsageContent,
    ElectricitySummary,
    ElectricityUsage,
    ElectricityPlans,
    ElectricityMeterReads,

    # Gas
    GasUsageContent,
    GasUsage,

    # Broadband
    BroadbandUsage,
)


class MercuryAPIClient:
    """
    Mercury.co.nz selfservice API Client

    Handles API calls to Mercury's selfservice endpoints for retrieving
    customer information, accounts, services, and other data.
    """

    def __init__(self, access_token: str, config: Optional[MercuryConfig] = None, verbose: bool = False):
        """
        Initialize the Mercury.co.nz API client

        Args:
            access_token: OAuth access token for API authentication
            config: Configuration object (uses default if None)
            verbose: Enable verbose logging output
        """
        self.access_token = access_token
        self.config = config or default_config
        self.verbose = verbose

        # Initialize API endpoints
        self.endpoints = MercuryAPIEndpoints(self.config.api_base_url)

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update(self._build_headers())

    def _log(self, message: str):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            print(message)

    def close(self) -> None:
        """Close the underlying HTTP session and release its connection pool."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _build_headers(self) -> Dict[str, str]:
        """Build headers for Mercury.co.nz API requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Ocp-Apim-Subscription-Key': self.config.api_subscription_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'https://myaccount.mercury.co.nz',
            'Referer': 'https://myaccount.mercury.co.nz/',
            'User-Agent': self.config.user_agent
        }

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an API request with error handling

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            MercuryAPIError: For various API errors
        """
        try:
            response = self.session.request(method, url, timeout=self.config.timeout, **kwargs)

            # Handle specific status codes
            if response.status_code == 401:
                raise MercuryAPIUnauthorizedError("API request unauthorized - check access token and subscription key")
            elif response.status_code == 404:
                raise MercuryAPINotFoundError(f"API endpoint not found: {url}")
            elif response.status_code == 429:
                raise MercuryAPIRateLimitError("API rate limit exceeded")
            elif response.status_code >= 400:
                raise MercuryAPIError(f"API request failed with status {response.status_code}: {response.text}")

            return response

        except requests.exceptions.RequestException as e:
            raise MercuryAPIConnectionError(f"API connection failed: {e}")

    def get_customer_info(self, customer_id: str) -> Optional[CustomerInfo]:
        """
        Get customer information

        Args:
            customer_id: Mercury.co.nz customer ID

        Returns:
            CustomerInfo object or None if not found
        """
        self._log(f"📊 Getting customer info for ID: {customer_id}")

        url = self.endpoints.customer_info(customer_id)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Customer info retrieved successfully")
            return CustomerInfo(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Customer info request returned {response.status_code}")
            return None

    def get_accounts(self, customer_id: str) -> List[Account]:
        """
        Get customer accounts

        Args:
            customer_id: Mercury.co.nz customer ID

        Returns:
            List of Account objects
        """
        self._log(f"🏦 Getting accounts for customer ID: {customer_id}")

        url = self.endpoints.customer_accounts(customer_id)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()

            # Handle both array and single object responses
            accounts_data = data if isinstance(data, list) else [data] if data else []
            accounts = [Account(account_data) for account_data in accounts_data]

            self._log(f"✅ Found {len(accounts)} account(s)")
            for i, account in enumerate(accounts):
                self._log(f"    {i+1}. Account ID: {account.account_id}, Name: {account.account_name}")

            return accounts
        else:  # pragma: no cover
            self._log(f"⚠️ Accounts request returned {response.status_code}")
            return []

    def get_services(self, customer_id: str, account_id: str, include_all: bool = False) -> List[Service]:
        """
        Get services for an account

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            include_all: Whether to include all services (default False)

        Returns:
            List of Service objects
        """
        self._log(f"🔧 Getting services for account ID: {account_id}")

        url = self.endpoints.account_services(customer_id, account_id, include_all)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()

            # Extract services from nested structure
            if isinstance(data, dict) and 'services' in data:
                services_data = data['services']
            elif isinstance(data, list):
                services_data = data
            else:
                services_data = []

            services = [Service(service_data) for service_data in services_data]

            self._log(f"✅ Found {len(services)} service(s) for account {account_id}")
            for service in services:
                self._log(f"    🔧 {service.service_group.title()}: {service.service_id}")

            return services
        else:  # pragma: no cover
            self._log(f"⚠️ Services request returned {response.status_code} for account {account_id}")
            return []

    def get_all_services(self, customer_id: str, account_ids: List[str]) -> List[Service]:
        """
        Get all services for multiple accounts

        Args:
            customer_id: Mercury.co.nz customer ID
            account_ids: List of Mercury.co.nz account IDs

        Returns:
            List of all Service objects across all accounts
        """
        all_services = []

        for account_id in account_ids:
            services = self.get_services(customer_id, account_id)
            all_services.extend(services)

        return all_services

    def get_service_ids(self, customer_id: str, account_ids: List[str]) -> ServiceIds:
        """
        Get organized service IDs for accounts

        Args:
            customer_id: Mercury.co.nz customer ID
            account_ids: List of Mercury.co.nz account IDs

        Returns:
            ServiceIds object with organized service IDs by type
        """
        all_services = self.get_all_services(customer_id, account_ids)
        return ServiceIds(all_services)

    def get_electricity_meter_info(self, customer_id: str, account_id: str) -> Optional[MeterInfo]:
        """
        Get electricity meter information for an account

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID

        Returns:
            MeterInfo object or None if not found
        """
        self._log(f"⚡ Getting electricity meter info for account: {account_id}")

        url = self.endpoints.electricity_meter_info(customer_id, account_id)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Electricity meter info retrieved successfully")

            return MeterInfo(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Meter info request returned {response.status_code} for account {account_id}")
            return None

    def get_bill_summary(self, customer_id: str, account_id: str) -> Optional[BillSummary]:
        """
        Get bill summary for an account

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID

        Returns:
            BillSummary object or None if not found
        """
        self._log(f"📄 Getting bill summary for account: {account_id}")

        url = self.endpoints.bill_summary(customer_id, account_id)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Bill summary retrieved successfully")

            return BillSummary(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Bill summary request returned {response.status_code} for account {account_id}")
            return None

    def get_electricity_usage_content(self) -> Optional[ElectricityUsageContent]:
        """
        Get electricity usage content from my-account

        Returns:
            ElectricityUsageContent object or None if not found
        """
        self._log(f"⚡ Getting electricity usage content...")

        url = self.endpoints.electricity_usage_content()
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Electricity usage content retrieved successfully")
            return ElectricityUsageContent(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Electricity usage content request returned {response.status_code}")
            return None

    def get_gas_usage_content(self) -> Optional[GasUsageContent]:
        """
        Get gas usage content from my-account

        Returns:
            GasUsageContent object or None if not found
        """
        self._log(f"🔥 Getting gas usage content...")

        url = self.endpoints.gas_usage_content()
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Gas usage content retrieved successfully")
            return GasUsageContent(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Gas usage content request returned {response.status_code}")
            return None

    def get_usage_content(self, service_type: str) -> Optional[Dict[str, Any]]:
        """
        Get usage content from my-account for any service type

        Args:
            service_type: Service type (e.g., 'Electricity', 'Gas')

        Returns:
            Raw usage content data or None if not found
        """
        self._log(f"📊 Getting {service_type.lower()} usage content...")

        url = self.endpoints.usage_content(service_type)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log(f"✅ {service_type} usage content retrieved successfully")
            return data
        else:  # pragma: no cover
            self._log(f"⚠️ {service_type} usage content request returned {response.status_code}")
            return None

    def get_service_usage(self, customer_id: str, account_id: str, service_type: str, service_id: str,
                         interval: str = 'daily',
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> Optional[ServiceUsage]:
        """
        Get service usage data for any service type (electricity, gas, etc.)

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_type: Service type ('electricity', 'gas', etc.)
            service_id: Service ID for the specific service
            interval: Data interval ('daily', 'hourly', 'monthly') - defaults to 'daily'
            start_date: Optional start date in format "2025-07-17T10:20:01+12:00" (URL-encoded).
                       If None, defaults to 14 days before end_date.
            end_date: Optional end date in format "2025-07-31T10:20:01+12:00" (URL-encoded).
                     If None, defaults to today's date in New Zealand timezone.

        Returns:
            ServiceUsage object or None if not found

        Note:
            Response includes usage data. Temperature data only available for electricity.
            Default period is 14 days ending today.
        """
        # Generate end date (today) if not provided
        nz_timezone = timezone(timedelta(hours=12))

        end_dt: Optional[datetime] = None
        if end_date is None:
            end_dt = datetime.now(nz_timezone).replace(hour=10, minute=20, second=1, microsecond=0)
            end_date = quote(end_dt.isoformat())
            self._log(f"🔥 Using today as end date: {end_dt.isoformat()}")

        # Generate start date (14 days before end date) if not provided
        if start_date is None:
            try:
                if end_dt is None:
                    # Parse the provided end_date (URL-decode first)
                    end_dt = datetime.fromisoformat(unquote(end_date))
                start_dt = end_dt - timedelta(days=14)
                start_date = quote(start_dt.isoformat())
                self._log(f"🔥 Using 14 days before as start date: {start_dt.isoformat()}")
            except (TypeError, ValueError) as e:
                self._log(f"⚠️ Error calculating start date: {e}")
                # Fallback: use a simple 14-day offset from now
                fallback_start = datetime.now(nz_timezone) - timedelta(days=14)
                start_date = quote(fallback_start.isoformat())

        self._log(f"🔥 Getting {service_type} usage for service {service_id} from {start_date} to {end_date}")

        url = self.endpoints.service_usage(customer_id, account_id, service_type, service_id, interval, start_date, end_date)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log(f"✅ {service_type.title()} usage data retrieved successfully")

            return ServiceUsage(data)
        else:  # pragma: no cover
            self._log(f"⚠️ {service_type.title()} usage request returned {response.status_code} for service {service_id}")
            return None

    def get_gas_usage(self, customer_id: str, account_id: str, service_id: str,
                     interval: str = 'daily',
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> Optional[GasUsage]:
        """
        Get gas usage data for a date range

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Gas service ID
            interval: Data interval ('daily', 'hourly', 'monthly') - defaults to 'daily'
            start_date: Optional start date in format "2025-07-17T10:20:01+12:00" (URL-encoded).
                       If None, defaults to 14 days before end_date.
            end_date: Optional end date in format "2025-07-31T10:20:01+12:00" (URL-encoded).
                     If None, defaults to today's date in New Zealand timezone.

        Returns:
            GasUsage object or None if not found

        Note:
            Response includes gas usage data. No temperature data for gas services.
            Default period is 14 days ending today.
        """
        # Use the generic service usage method
        service_usage = self.get_service_usage(customer_id, account_id, 'gas', service_id, interval, start_date, end_date)

        if service_usage:
            # Convert to GasUsage object
            return GasUsage(service_usage.raw_data)
        else:
            return None

    def get_electricity_summary(self, customer_id: str, account_id: str, service_id: str, as_of_date: Optional[str] = None) -> Optional[ElectricitySummary]:
        """
        Get electricity service summary for a specific date

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Electricity service ID
            as_of_date: Optional date in format "2025-07-31T00:00:00+12:00" (URL-encoded).
                       If None, defaults to today's date in New Zealand timezone.

        Returns:
            ElectricitySummary object or None if not found

        Note:
            Weekly summary starts on Monday and ends on Sunday.
            Daily total includes: Daily Fixed Charge + variable charge (actual electricity used) + GST.
        """
        # Generate today's date in New Zealand timezone if not provided
        if as_of_date is None:
            # New Zealand Standard Time (NZST) is UTC+12, Daylight Time (NZDT) is UTC+13
            # For simplicity, using UTC+12 as default (can be refined for daylight saving)
            nz_timezone = timezone(timedelta(hours=12))
            today = datetime.now(nz_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
            as_of_date = quote(today.isoformat())
            self._log(f"⚡ Using today's date: {today.isoformat()}")

        self._log(f"⚡ Getting electricity summary for service {service_id} as of {as_of_date}")

        url = self.endpoints.electricity_summary(customer_id, account_id, service_id, as_of_date)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Electricity summary retrieved successfully")

            return ElectricitySummary(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Electricity summary request returned {response.status_code} for service {service_id}")
            return None

    def get_electricity_usage(self, customer_id: str, account_id: str, service_id: str,
                            interval: str = 'daily',
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> Optional[ElectricityUsage]:
        """
        Get electricity usage data for a date range

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Electricity service ID
            interval: Data interval ('daily', 'hourly', etc.) - defaults to 'daily'
            start_date: Optional start date in format "2025-07-17T10:20:01+12:00" (URL-encoded).
                       If None, defaults to 14 days before end_date.
            end_date: Optional end date in format "2025-07-31T10:20:01+12:00" (URL-encoded).
                     If None, defaults to today's date in New Zealand timezone.

        Returns:
            ElectricityUsage object or None if not found

        Note:
            Response includes usage data and average temperature for each day.
            Default period is 14 days ending today.
        """
        # Use the generic service usage method
        service_usage = self.get_service_usage(customer_id, account_id, 'electricity', service_id, interval, start_date, end_date)

        if service_usage:
            # Convert to ElectricityUsage object
            return ElectricityUsage(service_usage.raw_data)
        else:
            return None

    def get_electricity_usage_hourly(self, customer_id: str, account_id: str, service_id: str,
                                   start_date: Optional[str] = None,
                                   end_date: Optional[str] = None) -> Optional[ElectricityUsage]:
        """
        Get hourly electricity usage data (defaults to 2-day period ending yesterday)

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Electricity service ID
            start_date: Optional start date in format "2025-07-27T00:00:00+12:00" (URL-encoded).
                       If None, defaults to 2 days before end_date.
            end_date: Optional end date in format "2025-07-29T00:00:00+12:00" (URL-encoded).
                     If None, defaults to yesterday (00:00:00 NZ timezone).

        Returns:
            ElectricityUsage object with hourly data or None if not found

        Note:
            Default period is 2 days ending yesterday to get complete hourly data.
            Hourly data is typically not available for today until the day is complete.
        """
        # Generate end date (yesterday) if not provided
        nz_timezone = timezone(timedelta(hours=12))

        end_dt: Optional[datetime] = None
        if end_date is None:
            end_dt = (datetime.now(nz_timezone) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = quote(end_dt.isoformat())
            self._log(f"⚡ Using yesterday as end date: {end_dt.isoformat()}")

        # Generate start date (2 days before end date) if not provided
        if start_date is None:
            try:
                if end_dt is None:
                    end_dt = datetime.fromisoformat(unquote(end_date))
                start_dt = end_dt - timedelta(days=2)
                start_date = quote(start_dt.isoformat())
                self._log(f"⚡ Using 2 days before as start date: {start_dt.isoformat()}")
            except (TypeError, ValueError) as e:
                self._log(f"⚠️ Error calculating start date: {e}")
                # Fallback: use a simple 2-day offset from now
                fallback_start = datetime.now(nz_timezone) - timedelta(days=3)
                start_date = quote(fallback_start.isoformat())

        self._log(f"⚡ Getting hourly electricity usage for service {service_id} from {start_date} to {end_date}")

        return self.get_electricity_usage(customer_id, account_id, service_id,
                                        interval='hourly',
                                        start_date=start_date,
                                        end_date=end_date)

    def get_electricity_usage_monthly(self, customer_id: str, account_id: str, service_id: str,
                                    start_date: Optional[str] = None,
                                    end_date: Optional[str] = None) -> Optional[ElectricityUsage]:
        """
        Get monthly electricity usage data (defaults to 1-year period ending today)

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Electricity service ID
            start_date: Optional start date in format "2024-07-31T10:46:54+12:00" (URL-encoded).
                       If None, defaults to 1 year before end_date.
            end_date: Optional end date in format "2025-07-31T10:46:54+12:00" (URL-encoded).
                     If None, defaults to today (current time in NZ timezone).

        Returns:
            ElectricityUsage object with monthly data or None if not found

        Note:
            Default period is 1 year ending today to get complete monthly usage trends.
            Monthly data provides long-term usage patterns and seasonal variations.
        """
        # Generate end date (today) if not provided
        nz_timezone = timezone(timedelta(hours=12))

        end_dt: Optional[datetime] = None
        if end_date is None:
            end_dt = datetime.now(nz_timezone)
            end_date = quote(end_dt.isoformat())
            self._log(f"⚡ Using today as end date: {end_dt.isoformat()}")

        # Generate start date (1 year before end date) if not provided
        if start_date is None:
            try:
                if end_dt is None:
                    end_dt = datetime.fromisoformat(unquote(end_date))
                start_dt = end_dt - timedelta(days=365)
                start_date = quote(start_dt.isoformat())
                self._log(f"⚡ Using 1 year before as start date: {start_dt.isoformat()}")
            except (TypeError, ValueError) as e:
                self._log(f"⚠️ Error calculating start date: {e}")
                # Fallback: use a simple 1-year offset from now
                fallback_start = datetime.now(nz_timezone) - timedelta(days=365)
                start_date = quote(fallback_start.isoformat())

        self._log(f"⚡ Getting monthly electricity usage for service {service_id} from {start_date} to {end_date}")

        return self.get_electricity_usage(customer_id, account_id, service_id,
                                        interval='monthly',
                                        start_date=start_date,
                                        end_date=end_date)

    def get_gas_usage_hourly(self, customer_id: str, account_id: str, service_id: str,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> Optional[GasUsage]:
        """
        Get hourly gas usage data (defaults to 2-day period ending yesterday)

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Gas service ID
            start_date: Optional start date in format "2025-07-27T00:00:00+12:00" (URL-encoded).
                       If None, defaults to 2 days before end_date.
            end_date: Optional end date in format "2025-07-29T00:00:00+12:00" (URL-encoded).
                     If None, defaults to yesterday (00:00:00 NZ timezone).

        Returns:
            GasUsage object with hourly data or None if not found

        Note:
            Default period is 2 days ending yesterday to get complete hourly data.
            Hourly data is typically not available for today until the day is complete.
        """
        return self.get_gas_usage(customer_id, account_id, service_id,
                                 interval='hourly',
                                 start_date=start_date,
                                 end_date=end_date)

    def get_gas_usage_monthly(self, customer_id: str, account_id: str, service_id: str,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> Optional[GasUsage]:
        """
        Get monthly gas usage data (defaults to 1-year period ending today)

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Gas service ID
            start_date: Optional start date in format "2024-07-31T10:46:54+12:00" (URL-encoded).
                       If None, defaults to 1 year before end_date.
            end_date: Optional end date in format "2025-07-31T10:46:54+12:00" (URL-encoded).
                     If None, defaults to today (current time in NZ timezone).

        Returns:
            GasUsage object with monthly data or None if not found

        Note:
            Default period is 1 year ending today to get complete monthly usage trends.
            Monthly data provides long-term usage patterns and seasonal variations.
        """
        return self.get_gas_usage(customer_id, account_id, service_id,
                                 interval='monthly',
                                 start_date=start_date,
                                 end_date=end_date)

    def get_broadband_usage(self, customer_id: str, account_id: str, service_id: str) -> Optional[BroadbandUsage]:
        """
        Get broadband (fibre) service information and usage data

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Broadband/Fibre service ID

        Returns:
            BroadbandUsage object containing service info and usage data or None if not found

        Note:
            Returns service information (plan name, plan code) and daily usage data.
            This endpoint provides both service details and usage in a single call.
        """
        self._log(f"🌐 Getting broadband service info and usage for service {service_id}")

        url = self.endpoints.broadband_service_info(customer_id, account_id, service_id)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Broadband service info and usage retrieved successfully")

            return BroadbandUsage(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Broadband service request returned {response.status_code} for service {service_id}")
            return None

    def get_fibre_usage(self, customer_id: str, account_id: str, service_id: str) -> Optional[BroadbandUsage]:
        """
        Get fibre broadband service information and usage data (alias for get_broadband_usage)

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Fibre service ID

        Returns:
            BroadbandUsage object containing service info and usage data or None if not found
        """
        return self.get_broadband_usage(customer_id, account_id, service_id)

    def get_electricity_plans(self, customer_id: str, account_id: str, service_id: str) -> Optional[ElectricityPlans]:
        """
        Get electricity plans and pricing information

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Electricity service ID

        Returns:
            ElectricityPlans object or None if not found

        Note:
            This method automatically retrieves the required ICP number from the services endpoint
            using the service 'identifier' field.
        """
        # Get ICP number from services endpoint (always automatic)
        self._log(f"⚡ Fetching ICP number from services...")
        services = self.get_services(customer_id, account_id)
        icp_number = None

        if services:
            # Find the electricity service and get its identifier (ICP)
            for service in services:
                if service.service_id == service_id and service.service_group.lower() == 'electricity':
                    # ICP is stored in the 'identifier' field of the service
                    icp_number = service.raw_data.get('identifier')
                    if icp_number:
                        self._log(f"⚡ Retrieved ICP number from service data: {icp_number}")
                        break

        if not icp_number:
            self._log(f"⚠️ Could not retrieve ICP number from services")
            return None

        self._log(f"⚡ Getting electricity plans for service {service_id} with ICP {icp_number}")

        url = self.endpoints.electricity_plans(customer_id, account_id, service_id, icp_number)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Electricity plans retrieved successfully")
            # Add the ICP number to the data for the ElectricityPlans class
            data['icp_number'] = icp_number
            data['service_id'] = service_id
            data['account_id'] = account_id
            return ElectricityPlans(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Electricity plans request returned {response.status_code} for service {service_id}")
            return None

    def get_electricity_meter_reads(self, customer_id: str, account_id: str, service_id: str) -> Optional[ElectricityMeterReads]:
        """
        Get electricity meter reads information

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_id: Electricity service ID

        Returns:
            ElectricityMeterReads object or None if not found

        Note:
            Provides historical meter readings, consumption data, and billing period information.
            Includes latest and previous readings with automatic consumption calculation.
        """
        self._log(f"⚡ Getting electricity meter reads for service {service_id}")

        url = self.endpoints.electricity_meter_reads(customer_id, account_id, service_id)
        response = self._make_request('GET', url)

        if response.status_code == 200:
            data = response.json()
            self._log("✅ Electricity meter reads retrieved successfully")

            # Debug: Check what type of data we're getting
            if isinstance(data, list):
                self._log(f"⚠️ API returned a list with {len(data)} items instead of a dict")
                # If it's a list, wrap it in a dict
                data = {'meterReads': data}
            elif not isinstance(data, dict):
                self._log(f"⚠️ API returned unexpected data type: {type(data)}")
                return None
            return ElectricityMeterReads(data)
        else:  # pragma: no cover
            self._log(f"⚠️ Electricity meter reads request returned {response.status_code} for service {service_id}")
            return None
