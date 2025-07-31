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

    def electricity_usage_content(self) -> str:
        """Get electricity usage content endpoint"""
        return f"{self.base_url}/content/my-account?path=Electricity%2FUsage"

    def electricity_summary(self, customer_id: str, account_id: str, service_id: str, as_of_date: str) -> str:
        """Get electricity service summary endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/summary?asOfDate={as_of_date}"

    def electricity_usage(self, customer_id: str, account_id: str, service_id: str, interval: str, start_date: str, end_date: str) -> str:
        """Get electricity usage data endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/usage?interval={interval}&startDate={start_date}&endDate={end_date}"

    def electricity_plans(self, customer_id: str, account_id: str, service_id: str, icp_number: str) -> str:
        """Get electricity plans and pricing endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/{icp_number}/plans"

    def electricity_meter_reads(self, customer_id: str, account_id: str, service_id: str) -> str:
        """Get electricity meter reads endpoint"""
        return f"{self.base_url}/customers/{customer_id}/accounts/{account_id}/services/electricity/{service_id}/meter-reads"
