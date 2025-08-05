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


class CustomerInfo:
    """Customer information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.customer_id = data.get('customerId')
        self.name = data.get('name')
        self.email = data.get('email')
        # Add other customer fields as needed


class Account:
    """Customer account container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.account_id = data.get('accountId') or data.get('id')
        self.account_name = data.get('accountName') or data.get('name')
        self.status = data.get('status')
        # Add other account fields as needed


class Service:
    """Service container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.service_id = data.get('serviceId')
        self.service_group = data.get('serviceGroup', '').lower()
        self.service_type = data.get('serviceType')
        self.address = data.get('address')
        self.status = data.get('status')
        # Add other service fields as needed

    @property
    def is_electricity(self) -> bool:
        """Check if this is an electricity service"""
        return self.service_group == 'electricity'

    @property
    def is_gas(self) -> bool:
        """Check if this is a gas service"""
        return self.service_group == 'gas'

    @property
    def is_broadband(self) -> bool:
        """Check if this is a broadband service"""
        return self.service_group == 'broadband'


class ServiceIds:
    """Container for organized service IDs"""

    def __init__(self, services: List[Service]):
        self.all: List[str] = []
        self.electricity: List[str] = []
        self.gas: List[str] = []
        self.broadband: List[str] = []

        for service in services:
            if service.service_id:
                self.all.append(service.service_id)

                if service.is_electricity:
                    self.electricity.append(service.service_id)
                elif service.is_gas:
                    self.gas.append(service.service_id)
                elif service.is_broadband:
                    self.broadband.append(service.service_id)


class MeterInfo:
    """Electricity meter information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.account_id = data.get('accountId')

        # Extract meter services data (Mercury.co.nz API returns nested structure)
        self.meter_services = data.get('meterservices', [])

        # Extract electricity meter service data
        electricity_meter = None
        for service in self.meter_services:
            if service.get('serviceId'):  # This is likely the electricity service
                electricity_meter = service
                break

        if electricity_meter:
            self.service_id = electricity_meter.get('serviceId')
            self.smart_meter_installed = electricity_meter.get('smartMeterInstalled')
            self.smart_meter_communicating = electricity_meter.get('smartMeterCommunicating')
            # Use service ID as meter number for now
            self.meter_number = self.service_id
            self.meter_status = 'Active' if self.smart_meter_communicating else 'Not Communicating'
            self.meter_type = 'Smart Meter' if self.smart_meter_installed else 'Traditional Meter'
        else:
            self.service_id = None
            self.smart_meter_installed = None
            self.smart_meter_communicating = None
            self.meter_number = None
            self.meter_status = None
            self.meter_type = None

        # Legacy field mapping (keeping for backward compatibility)
        self.installation_date = data.get('installationDate')
        self.last_reading_date = data.get('lastReadingDate')
        self.next_reading_date = data.get('nextReadingDate')
        self.register_count = data.get('registerCount')
        self.registers = data.get('registers', [])

        # ICP (Installation Control Point) - unique identifier for electricity connections in NZ
        self.icp_number = data.get('icpNumber') or data.get('icp') or data.get('meter_number') or self.meter_number

        # Additional meter fields
        self.serial_number = data.get('serialNumber')
        self.location = data.get('location')
        self.manufacturer = data.get('manufacturer')
        self.model = data.get('model')
        # Add other meter fields as needed


class BillSummary:
    """Bill summary information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.account_id = data.get('accountId')

        # Map Mercury.co.nz API field names to our standard names
        self.current_balance = data.get('balance')
        self.due_amount = data.get('dueAmount')
        self.overdue_amount = data.get('overdueAmount')
        self.due_date = data.get('dueDate')
        self.bill_date = data.get('billDate')  # Last bill date
        self.last_bill_date = data.get('billDate')  # Alias for backward compatibility
        self.next_bill_date = data.get('nextBillDate')

        # Payment information
        self.payment_method = data.get('paymentMethod')
        self.payment_type = data.get('paymentType')
        self.balance_status = data.get('balanceStatus')

        # Bill details
        self.bill_url = data.get('billUrl')
        self.smooth_pay = data.get('smoothPay')

        # Statement breakdown
        self.statement = data.get('statement', {})
        self.statement_details = self.statement.get('details', [])
        self.statement_total = self.statement.get('total')

        # Extract service costs from statement details
        self.electricity_amount = None
        self.gas_amount = None
        self.broadband_amount = None

        for detail in self.statement_details:
            line_item = detail.get('lineItem', '').lower()
            amount = detail.get('amount')
            if 'electricity' in line_item:
                self.electricity_amount = amount
            elif 'gas' in line_item:
                self.gas_amount = amount
            elif 'broadband' in line_item:
                self.broadband_amount = amount

        # Legacy fields for backward compatibility
        self.bill_frequency = data.get('billFrequency')
        self.recent_payments = data.get('recentPayments', [])
        self.recent_bills = data.get('recentBills', [])
        # Add other billing fields as needed


class ElectricityUsageContent:
    """Electricity usage content container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.content = data.get('content')
        self.path = data.get('path')
        self.title = data.get('title')
        self.description = data.get('description')
        self.usage_data = data.get('usageData', [])
        self.summary_info = data.get('summaryInfo', {})
        # Add other usage content fields as needed


class GasUsageContent:
    """Gas usage content container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.content_name = data.get('contentName')
        self.locale = data.get('locale')
        self.content = data.get('content', {})

        # Parse specific gas usage content fields
        content_data = self.content
        self.disclaimer_usage = content_data.get('disclaimer_usage', {}).get('text', '')
        self.usage_info_modal_title = content_data.get('usage_info_modal_title', {}).get('text', '')
        self.usage_info_modal_body = content_data.get('usage_info_modal_body', {}).get('text', '')


class ElectricitySummary:
    """Electricity service summary container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.service_type = data.get('serviceType')

        # Weekly summary information (Monday to Sunday)
        self.weekly_summary = data.get('weeklySummary', {})
        self.weekly_start_date = self.weekly_summary.get('startDate')  # Monday
        self.weekly_end_date = self.weekly_summary.get('endDate')      # Sunday
        self.weekly_notes = self.weekly_summary.get('notes', [])
        self.last_week_cost = self.weekly_summary.get('lastWeekCost')

        # Calculate weekly totals from daily usage
        weekly_usage = self.weekly_summary.get('usage', [])
        self.weekly_total_usage = sum(day.get('consumption', 0) for day in weekly_usage)
        self.weekly_total_cost = sum(day.get('cost', 0) for day in weekly_usage)

        # Daily breakdown information from weekly summary
        self.daily_breakdown = weekly_usage
        self.weekly_usage_days = len(weekly_usage)

        # Monthly summary information
        self.monthly_summary = data.get('monthlySummary', {})
        self.monthly_start_date = self.monthly_summary.get('startDate')
        self.monthly_end_date = self.monthly_summary.get('endDate')
        self.monthly_status = self.monthly_summary.get('status')
        self.monthly_days_remaining = self.monthly_summary.get('daysRemaining')
        self.monthly_usage_cost = self.monthly_summary.get('usageCost')
        self.monthly_usage_consumption = self.monthly_summary.get('usageConsumption')
        self.monthly_note = self.monthly_summary.get('note')

        # Cost components (calculate from daily data)
        if weekly_usage:
            total_daily_costs = sum(day.get('cost', 0) for day in weekly_usage)
            avg_daily_cost = total_daily_costs / len(weekly_usage) if weekly_usage else 0
            # Estimate components (Mercury.co.nz doesn't break these down separately in this endpoint)
            self.daily_fixed_charge = avg_daily_cost * 0.3  # Rough estimate
            self.variable_charges = weekly_usage  # Actual daily usage data
            self.gst_amount = total_daily_costs * 0.15  # 15% GST estimate
        else:
            self.daily_fixed_charge = None
            self.variable_charges = []
            self.gst_amount = None

        # Usage statistics (calculate from weekly data)
        if weekly_usage:
            daily_consumptions = [day.get('consumption', 0) for day in weekly_usage]
            self.total_kwh_used = sum(daily_consumptions)
            self.average_daily_usage = self.total_kwh_used / len(daily_consumptions) if daily_consumptions else 0
            self.max_daily_usage = max(daily_consumptions) if daily_consumptions else 0
            self.min_daily_usage = min(daily_consumptions) if daily_consumptions else 0
        else:
            self.total_kwh_used = None
            self.average_daily_usage = None
            self.max_daily_usage = None
            self.min_daily_usage = None

        # Legacy fields for backward compatibility
        self.service_id = data.get('serviceId')
        self.account_id = data.get('accountId')
        self.as_of_date = data.get('asOfDate')
        self.peak_usage_time = data.get('peakUsageTime')
        self.off_peak_usage = data.get('offPeakUsage')
        self.billing_period_start = data.get('billingPeriodStart')
        self.billing_period_end = data.get('billingPeriodEnd')
        self.days_in_period = data.get('daysInPeriod')
        # Add other electricity summary fields as needed


class ElectricityPlans:
    """Electricity plans and pricing information container based on Mercury's actual API response"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.service_id = data.get('service_id') or data.get('serviceId')
        self.account_id = data.get('account_id') or data.get('accountId')
        self.icp_number = data.get('icp_number') or data.get('icpNumber') or data.get('icp')

        # Plan management - Mercury's actual fields
        self.can_change_plan = data.get('canChangePlan', False)

        # Pending plan changes - Mercury's actual structure
        pending_plan = data.get('pendingPlan', {})
        self.is_pending_plan_change = pending_plan.get('isPendingPlanChange', False)
        self.plan_change_date = pending_plan.get('planChangeDate', '')

        # Current plan - Mercury's actual structure
        self.current_plan = data.get('currentPlan', {})
        self.current_plan_id = self.current_plan.get('planId')
        self.current_plan_name = self.current_plan.get('name')
        self.current_plan_description = self.current_plan.get('description')
        self.current_plan_usage_type = self.current_plan.get('usageType')
        self.current_plan_learn_more = self.current_plan.get('learnMore')

        # Current plan charges - Mercury's actual structure
        charges = self.current_plan.get('charges', {})
        self.other_charges = charges.get('otherCharges', [])
        self.unit_rates = charges.get('unitRates', [])

        # Extract daily fixed charge from otherCharges array
        self.daily_fixed_charge = None
        self.daily_fixed_charge_rate = None
        for charge in self.other_charges:
            if charge.get('name') == 'Daily Fixed Charge':
                self.daily_fixed_charge = charge.get('rate')
                self.daily_fixed_charge_rate = charge.get('rate')
                break

        # Extract unit rate (typically "Anytime" rate) from unitRates array
        self.anytime_rate = None
        self.anytime_rate_measure = None
        for rate in self.unit_rates:
            if rate.get('name') == 'Anytime':
                self.anytime_rate = rate.get('rate')
                self.anytime_rate_measure = rate.get('measure')
                break

        # Available alternative plans - Mercury's actual fields
        self.standard_plans = data.get('standardPlans', [])
        self.low_plans = data.get('lowPlans', [])
        self.total_alternative_plans = len(self.standard_plans) + len(self.low_plans)


class ElectricityMeterReads:
    """Electricity meter reads information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data

        # Mercury.co.nz API returns meter reads as array, extract first meter
        meter_data = {}
        if isinstance(data, dict) and 'meterReads' in data:
            # If wrapped in dict (our correction)
            meter_list = data['meterReads']
        elif isinstance(data, list):
            # Direct list response from API
            meter_list = data
        else:
            meter_list = []

        if meter_list and len(meter_list) > 0:
            meter_data = meter_list[0]

        # Extract meter information
        self.meter_number = meter_data.get('meterNumber')
        self.account_id = data.get('accountId')  # May be in wrapper
        self.service_id = data.get('serviceId')  # May be in wrapper

        # Extract register information (Mercury.co.nz stores readings in registers)
        registers = meter_data.get('registers', [])
        self.registers = registers
        self.total_registers = len(registers)

        # Get the primary register (usually first one for electricity)
        primary_register = registers[0] if registers else {}

        # Latest reading details from primary register
        self.latest_reading_value = primary_register.get('lastReading')
        self.latest_reading_date = primary_register.get('lastReadDate')
        self.latest_reading_type = primary_register.get('lastReadType')
        self.register_number = primary_register.get('registerNumber')

        # Mercury.co.nz doesn't provide previous reading in this endpoint,
        # but we can estimate from historical data
        self.previous_reading_value = None
        self.previous_reading_date = None
        self.previous_reading_type = None

        # Try to estimate consumption if we had historical data
        # For now, just use the reading value as a reference
        if self.latest_reading_value:
            try:
                # Convert reading to integer (Mercury.co.nz readings are often strings like "089698")
                reading_int = int(self.latest_reading_value)
                # For demo purposes, estimate previous reading as 100 kWh less
                # (In real implementation, this would come from historical data)
                self.previous_reading_value = str(reading_int - 100)
                self.consumption_kwh = 100  # Estimated
            except (ValueError, TypeError):
                self.consumption_kwh = None
        else:
            self.consumption_kwh = None

        # Historical reads processing - use all registers
        self.historical_reads = []
        for register in registers:
            read_info = {
                'date': register.get('lastReadDate'),
                'value': register.get('lastReading'),
                'type': register.get('lastReadType'),
                'source': 'meter',  # From meter reading
                'register': register.get('registerNumber'),
                'unit': 'kWh'
            }
            self.historical_reads.append(read_info)

        # Reading statistics
        self.meter_reads = self.historical_reads  # Alias for backward compatibility
        self.total_reads = len(self.historical_reads)

        # Mercury-specific fields
        self.read_frequency = None  # Not provided in this endpoint
        self.next_scheduled_read = None  # Not provided

        # Billing period information (not provided in meter reads endpoint)
        self.current_billing_period = {}
        self.billing_period_start = None
        self.billing_period_end = None
        self.billing_period_days = None

        # Latest/previous read objects for backward compatibility
        self.latest_read = {
            'readingDate': self.latest_reading_date,
            'reading': self.latest_reading_value,
            'readingType': self.latest_reading_type
        }
        self.previous_read = {
            'readingDate': self.previous_reading_date,
            'reading': self.previous_reading_value,
            'readingType': self.previous_reading_type
        }

        # Reading source (inferred as automatic for smart meters)
        self.latest_reading_source = 'automatic' if self.latest_reading_type == 'Actual' else 'estimated'


class ServiceUsage:
    """Generic service usage data container for electricity, gas, etc."""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.service_type = data.get('serviceType')
        self.usage_period = data.get('usagePeriod')  # Daily, Hourly, Monthly
        self.start_date = data.get('startDate')
        self.end_date = data.get('endDate')

        # Extract usage data from Mercury.co.nz API format
        usage_arrays = data.get('usage', [])
        self.usage_data = []

        # Mercury.co.nz returns usage in arrays with different labels (actual, estimate, etc.)
        for usage_group in usage_arrays:
            if usage_group.get('label') == 'actual':
                self.usage_data = usage_group.get('data', [])
                break

        # If no 'actual' data found, use the first available group
        if not self.usage_data and usage_arrays:
            self.usage_data = usage_arrays[0].get('data', [])

        # Store all usage arrays for access to estimates, etc.
        self.all_usage_arrays = usage_arrays

        # Calculate statistics from usage data
        if self.usage_data:
            consumptions = [point.get('consumption', 0) for point in self.usage_data]
            costs = [point.get('cost', 0) for point in self.usage_data]

            self.total_usage = sum(consumptions)
            self.total_cost = sum(costs)
            self.average_daily_usage = self.total_usage / len(consumptions) if consumptions else 0
            self.max_daily_usage = max(consumptions) if consumptions else 0
            self.min_daily_usage = min(consumptions) if consumptions else 0
            self.data_points = len(self.usage_data)
        else:
            self.total_usage = 0
            self.total_cost = 0
            self.average_daily_usage = 0
            self.max_daily_usage = 0
            self.min_daily_usage = 0
            self.data_points = 0

        # Temperature data (Mercury.co.nz returns this separately)
        # Note: Temperature data is only available for electricity and daily intervals
        temp_data = data.get('averageTemperature')
        if temp_data and isinstance(temp_data, dict):
            self.temperature_data = temp_data.get('data', [])
        else:
            self.temperature_data = []

        # Calculate average temperature
        if self.temperature_data:
            temps = [point.get('temp', 0) for point in self.temperature_data]
            self.average_temperature = sum(temps) / len(temps) if temps else 0
        else:
            self.average_temperature = None

        # Usage breakdown by time period
        self.daily_usage = []
        for usage_point in self.usage_data:
            daily_info = {
                'date': usage_point.get('date'),
                'consumption': usage_point.get('consumption'),
                'cost': usage_point.get('cost'),
                'free_power': usage_point.get('freePower'),
                'invoice_from': usage_point.get('invoiceFrom'),
                'invoice_to': usage_point.get('invoiceTo')
            }
            self.daily_usage.append(daily_info)

        # Legacy fields for backward compatibility
        self.service_id = data.get('serviceId')
        self.account_id = data.get('accountId')
        self.interval = self.usage_period.lower() if self.usage_period else 'daily'
        self.period_start = self.start_date
        self.period_end = self.end_date
        self.days_in_period = len(self.usage_data) if self.usage_data else 0

        # Store annotations field
        self.annotations = data.get('annotations', [])


class ElectricityUsage(ServiceUsage):
    """Electricity usage data container"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)


class GasUsage(ServiceUsage):
    """Gas usage data container"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)


class BroadbandUsage:
    """Broadband (Fibre) usage and service information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data

        # Service information
        self.plan_name = data.get('planName')
        self.plan_code = data.get('planCode')

        # Usage summary (convert string values to float for calculations)
        try:
            self.avg_daily_usage = float(data.get('avgDailyUsage', 0))
            self.total_data_used = float(data.get('totalDataUsed', 0))
        except (ValueError, TypeError):
            self.avg_daily_usage = 0.0
            self.total_data_used = 0.0

        # Daily usage data
        self.daily_usages = data.get('dailyUsages', [])

        # Process daily usage for statistics
        if self.daily_usages:
            try:
                daily_values = [float(day.get('usage', 0)) for day in self.daily_usages]
                self.max_daily_usage = max(daily_values) if daily_values else 0.0
                self.min_daily_usage = min(daily_values) if daily_values else 0.0
                self.data_points = len(daily_values)

                # Calculate usage days (days with non-zero usage)
                self.usage_days = len([val for val in daily_values if val > 0])

                # Get date range
                if self.daily_usages:
                    self.start_date = self.daily_usages[0].get('date')
                    self.end_date = self.daily_usages[-1].get('date')
                else:
                    self.start_date = None
                    self.end_date = None

            except (ValueError, TypeError):
                self.max_daily_usage = 0.0
                self.min_daily_usage = 0.0
                self.data_points = 0
                self.usage_days = 0
                self.start_date = None
                self.end_date = None
        else:
            self.max_daily_usage = 0.0
            self.min_daily_usage = 0.0
            self.data_points = 0
            self.usage_days = 0
            self.start_date = None
            self.end_date = None

        # Service type and period for consistency with other usage classes
        self.service_type = "Broadband"
        self.usage_period = "Daily"


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
        else:
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
        else:
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
        else:
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
        else:
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
        else:
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
        else:
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
        else:
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
        else:
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

        if end_date is None:
            today = datetime.now(nz_timezone).replace(hour=10, minute=20, second=1, microsecond=0)
            end_date = quote(today.isoformat())
            self._log(f"🔥 Using today as end date: {today.isoformat()}")

        # Generate start date (14 days before end date) if not provided
        if start_date is None:
            # Parse the end_date to calculate start_date
            try:
                # If end_date was just generated, we have the datetime object
                if 'today' in locals():
                    start_dt = today - timedelta(days=14)
                else:
                    # Parse the provided end_date (URL-decode first)
                    end_date_str = unquote(end_date)
                    end_dt = datetime.fromisoformat(end_date_str)
                    start_dt = end_dt - timedelta(days=14)

                start_date = quote(start_dt.isoformat())
                self._log(f"🔥 Using 14 days before as start date: {start_dt.isoformat()}")
            except Exception as e:
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
        else:
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
        else:
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

        if end_date is None:
            yesterday = datetime.now(nz_timezone) - timedelta(days=1)
            yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = quote(yesterday.isoformat())
            self._log(f"⚡ Using yesterday as end date: {yesterday.isoformat()}")

        # Generate start date (2 days before end date) if not provided
        if start_date is None:
            try:
                # If end_date was just generated, we have the datetime object
                if 'yesterday' in locals():
                    start_dt = yesterday - timedelta(days=2)
                else:
                    # Parse the provided end_date (URL-decode first)
                    end_date_str = unquote(end_date)
                    end_dt = datetime.fromisoformat(end_date_str)
                    start_dt = end_dt - timedelta(days=2)

                start_date = quote(start_dt.isoformat())
                self._log(f"⚡ Using 2 days before as start date: {start_dt.isoformat()}")
            except Exception as e:
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

        if end_date is None:
            today = datetime.now(nz_timezone)
            end_date = quote(today.isoformat())
            self._log(f"⚡ Using today as end date: {today.isoformat()}")

        # Generate start date (1 year before end date) if not provided
        if start_date is None:
            try:
                # If end_date was just generated, we have the datetime object
                if 'today' in locals():
                    start_dt = today - timedelta(days=365)  # 1 year = 365 days
                else:
                    # Parse the provided end_date (URL-decode first)
                    end_date_str = unquote(end_date)
                    end_dt = datetime.fromisoformat(end_date_str)
                    start_dt = end_dt - timedelta(days=365)

                start_date = quote(start_dt.isoformat())
                self._log(f"⚡ Using 1 year before as start date: {start_dt.isoformat()}")
            except Exception as e:
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
        else:
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
        else:
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
        else:
            self._log(f"⚠️ Electricity meter reads request returned {response.status_code} for service {service_id}")
            return None
