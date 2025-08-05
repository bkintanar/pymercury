#!/usr/bin/env python3
"""
Mercury.co.nz Library

A comprehensive Python library for interacting with Mercury.co.nz services,
including OAuth authentication and selfservice API integration.

Usage Examples:

Simple authentication:
    from mercury import authenticate
    tokens = authenticate("email@example.com", "password")

Complete account data:
    from mercury import get_complete_data
    data = get_complete_data("email@example.com", "password")
    customer_id = data.customer_id
    account_ids = data.account_ids
    electricity_services = data.service_ids.electricity

Advanced usage with main client:
    from mercury import MercuryClient
    client = MercuryClient("email@example.com", "password")
    client.login()

    # Easy access to IDs
    customer_id = client.customer_id
    account_ids = client.account_ids
    service_ids = client.service_ids

    # Get complete data
    data = client.get_complete_account_data()

Separate OAuth and API clients:
    from mercury.oauth import MercuryOAuthClient
    from mercury.api import MercuryAPIClient

    # OAuth only
    oauth = MercuryOAuthClient("email@example.com", "password")
    tokens = oauth.authenticate()

    # API only (with existing tokens)
    api = MercuryAPIClient(tokens.access_token)
    accounts = api.get_accounts(tokens.customer_id)

Configuration:
    from mercury import MercuryConfig, MercuryClient

    config = MercuryConfig(
        api_subscription_key="your-key",
        timeout=30
    )
    client = MercuryClient("email@example.com", "password", config)
"""

# Main client (recommended for most users)
from .client import MercuryClient, CompleteAccountData, authenticate, get_complete_data

# OAuth functionality
from .oauth import MercuryOAuthClient, OAuthTokens

# API functionality
from .api import (
    MercuryAPIClient,
    CustomerInfo,
    Account,
    Service,
    ServiceIds,
    MeterInfo,
    BillSummary,
    ElectricityUsageContent,
    GasUsageContent,
    ServiceUsage,
    ElectricitySummary,
    ElectricityUsage,
    GasUsage,
    BroadbandUsage,
    ElectricityPlans,
    ElectricityMeterReads
)

# Configuration and exceptions
from .config import MercuryConfig
from .exceptions import (
    MercuryError,
    MercuryConfigError,
    MercuryOAuthError,
    MercuryAuthenticationError,
    MercuryAPIError,
    MercuryAPIConnectionError,
    MercuryAPIUnauthorizedError,
    MercuryAPINotFoundError,
    MercuryAPIRateLimitError
)

# Version info
__version__ = "1.0.0"
__author__ = "Bertrand Kintanar <bertrand.kintanar@gmail.com>"
__description__ = "Python library for Mercury.co.nz OAuth and API integration"

# Main exports (what users get with "from mercury import *")
__all__ = [
    # Main client (recommended)
    'MercuryClient',
    'CompleteAccountData',
    'authenticate',
    'get_complete_data',

    # OAuth
    'MercuryOAuthClient',
    'OAuthTokens',

    # API
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

    # Configuration
    'MercuryConfig',

    # Exceptions
    'MercuryError',
    'MercuryConfigError',
    'MercuryOAuthError',
    'MercuryAuthenticationError',
    'MercuryAPIError',
    'MercuryAPIConnectionError',
    'MercuryAPIUnauthorizedError',
    'MercuryAPINotFoundError',
    'MercuryAPIRateLimitError',
]
