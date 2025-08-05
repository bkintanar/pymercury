#!/usr/bin/env python3
"""
Mercury.co.nz API Package

Mercury.co.nz selfservice API functionality.
"""

from .client import MercuryAPIClient
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
    'GasUsageContent',
    'ServiceUsage',
    'ElectricitySummary',
    'ElectricityUsage',
    'GasUsage',
    'BroadbandUsage',
    'ElectricityPlans',
    'ElectricityMeterReads',
    'MercuryAPIEndpoints'
]
