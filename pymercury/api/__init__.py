#!/usr/bin/env python3
"""
Mercury.co.nz API Package

Mercury.co.nz selfservice API functionality.
"""

from .client import MercuryAPIClient, CustomerInfo, Account, Service, ServiceIds, MeterInfo, BillSummary, ElectricityUsageContent, ElectricitySummary, ElectricityUsage, ElectricityPlans, ElectricityMeterReads
from .endpoints import MercuryAPIEndpoints

__all__ = [
    'MercuryAPIClient',
    'CustomerInfo',
    'Account',
    'Service',
    'ServiceIds',
    'MeterInfo',
    'BillSummary',
    'ElectricityUsageContent',
    'ElectricitySummary',
    'ElectricityUsage',
    'ElectricityPlans',
    'ElectricityMeterReads',
    'MercuryAPIEndpoints'
]
