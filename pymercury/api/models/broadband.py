#!/usr/bin/env python3
"""
Broadband Models for Mercury.co.nz API

Contains broadband/fibre-specific data classes and models.
"""

from typing import Dict, Any


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
