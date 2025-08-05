#!/usr/bin/env python3
"""
Mercury.co.nz API Endpoints

Definitions for Mercury.co.nz selfservice API endpoints.
"""

from typing import Dict, Any


class MercuryAPIEndpoints:
    """Mercury.co.nz selfservice API endpoint definitions"""

    def __init__(self, base_url: str):
        """
        Initialize API endpoints

        Args:
            base_url: Base URL for Mercury.co.nz selfservice API
        """
        self.base_url = base_url.rstrip('/')

    def customer_info(self, customer_id: str) -> str:
        """Get customer information endpoint"""
        return f"{self.base_url}/customers/{customer_id}"

    def customer_accounts(self, customer_id: str) -> str:
        """Get customer accounts endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts"

    def account_services(self, customer_id: str, account_id: str, include_all: bool = False) -> str:
        """Get account services endpoint"""
        url = f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services"
        if not include_all:
            url += "?includeAll=false"
        return url

    # Future endpoints can be added here
    def account_bills(self, customer_id: str, account_id: str) -> str:
        """Get account bills endpoint (future)"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/bills"

    def service_usage(self, customer_id: str, service_id: str) -> str:
        """Get service usage endpoint (future)"""
        return f"{self.base_url}/customers/{customer_id}/services/{service_id}/usage"

    def service_meter_readings(self, customer_id: str, service_id: str) -> str:
        """Get service meter readings endpoint (future)"""
        return f"{self.base_url}/customers/{customer_id}/services/{service_id}/meter-readings"

    def electricity_meter_info(self, customer_id: str, account_id: str) -> str:
        """Get electricity meter info endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/meter-info"

    def bill_summary(self, customer_id: str, account_id: str) -> str:
        """Get bill summary endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/bill-summary"

    def usage_content(self, service_type: str) -> str:
        """
        Get usage content endpoint for any service type

        Args:
            service_type: Service type (e.g., 'Electricity', 'Gas')

        Returns:
            URL for the usage content endpoint
        """
        return f"{self.base_url}/content/my-account?path={service_type}%2FUsage"

    def electricity_usage_content(self) -> str:
        """Get electricity usage content endpoint"""
        return self.usage_content("Electricity")

    def gas_usage_content(self) -> str:
        """Get gas usage content endpoint"""
        return self.usage_content("Gas")

    def electricity_summary(self, customer_id: str, account_id: str, service_id: str, as_of_date: str) -> str:
        """Get electricity service summary endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/summary?asOfDate={as_of_date}"

    def service_usage(self, customer_id: str, account_id: str, service_type: str, service_id: str, interval: str, start_date: str, end_date: str) -> str:
        """
        Get service usage data endpoint for any service type

        Args:
            customer_id: Mercury.co.nz customer ID
            account_id: Mercury.co.nz account ID
            service_type: Service type (e.g., 'electricity', 'gas')
            service_id: Service ID
            interval: Data interval ('daily', 'hourly', 'monthly')
            start_date: Start date (URL-encoded)
            end_date: End date (URL-encoded)

        Returns:
            URL for the service usage endpoint
        """
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/{service_type.lower()}/{service_id}/usage?interval={interval}&startDate={start_date}&endDate={end_date}"

    def electricity_usage(self, customer_id: str, account_id: str, service_id: str, interval: str, start_date: str, end_date: str) -> str:
        """Get electricity usage data endpoint"""
        return self.service_usage(customer_id, account_id, "electricity", service_id, interval, start_date, end_date)

    def gas_usage(self, customer_id: str, account_id: str, service_id: str, interval: str, start_date: str, end_date: str) -> str:
        """Get gas usage data endpoint"""
        return self.service_usage(customer_id, account_id, "gas", service_id, interval, start_date, end_date)

    def electricity_plans(self, customer_id: str, account_id: str, service_id: str, icp_number: str) -> str:
        """Get electricity plans and pricing endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/{icp_number}/plans"

    def electricity_meter_reads(self, customer_id: str, account_id: str, service_id: str) -> str:
        """Get electricity meter reads endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/meter-reads"

    def fibre_service_info(self, customer_id: str, account_id: str, service_id: str) -> str:
        """Get fibre broadband service information and usage data endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/fibre/{service_id}"

    def broadband_service_info(self, customer_id: str, account_id: str, service_id: str) -> str:
        """Get broadband service information and usage data endpoint (alias for fibre)"""
        return self.fibre_service_info(customer_id, account_id, service_id)
