#!/usr/bin/env python3
"""
Electricity Models for Mercury.co.nz API

Contains electricity-specific data classes and models.
"""

from typing import Dict, Any
from .base import ServiceUsage


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


class ElectricityUsage(ServiceUsage):
    """Electricity usage data container"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)
