#!/usr/bin/env python3
"""
Mercury.co.nz API Models Package

Contains all data model classes organized by service type.
"""

# Base classes
from .base import ServiceUsage

# Account management models
from .account import CustomerInfo, Account, Service, ServiceIds

# Billing and meter models
from .billing import MeterInfo, BillSummary

# Electricity service models
from .electricity import (
    ElectricityUsageContent,
    ElectricitySummary,
    ElectricityUsage,
    ElectricityPlans,
    ElectricityMeterReads
)

# Gas service models
from .gas import GasUsageContent, GasUsage

# Broadband service models
from .broadband import BroadbandUsage

# Export all models
__all__ = [
    # Base
    'ServiceUsage',

    # Account management
    'CustomerInfo',
    'Account',
    'Service',
    'ServiceIds',

    # Billing and meter
    'MeterInfo',
    'BillSummary',

    # Electricity
    'ElectricityUsageContent',
    'ElectricitySummary',
    'ElectricityUsage',
    'ElectricityPlans',
    'ElectricityMeterReads',

    # Gas
    'GasUsageContent',
    'GasUsage',

    # Broadband
    'BroadbandUsage',
]
