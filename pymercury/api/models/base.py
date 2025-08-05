#!/usr/bin/env python3
"""
Base Models for Mercury.co.nz API

Contains shared base classes and common functionality.
"""

from typing import Dict, Any


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
