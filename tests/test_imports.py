#!/usr/bin/env python3
"""
Import validation tests - converted from legacy test_mercury_library.py
"""

import pytest


class TestImports:
    """Test all import functionality"""

    def test_main_package_imports(self):
        """Test main package imports work correctly"""
        from pymercury import (
            MercuryClient,
            MercuryOAuthClient,
            MercuryAPIClient,
            authenticate,
            get_complete_data,
            MercuryConfig,
            CompleteAccountData,
            OAuthTokens
        )

        # Verify classes can be referenced
        assert MercuryClient is not None
        assert MercuryOAuthClient is not None
        assert MercuryAPIClient is not None
        assert authenticate is not None
        assert get_complete_data is not None
        assert MercuryConfig is not None
        assert CompleteAccountData is not None
        assert OAuthTokens is not None

    def test_api_data_classes_imports(self):
        """Test API data classes import correctly"""
        from pymercury import (
            CustomerInfo,
            Account,
            Service,
            ServiceIds,
            MeterInfo,
            BillSummary,
            ElectricityUsageContent,
            ElectricitySummary,
            ElectricityUsage,
            ElectricityPlans,
            ElectricityMeterReads
        )

        # Verify all classes are importable
        assert CustomerInfo is not None
        assert Account is not None
        assert Service is not None
        assert ServiceIds is not None
        assert MeterInfo is not None
        assert BillSummary is not None
        assert ElectricityUsageContent is not None
        assert ElectricitySummary is not None
        assert ElectricityUsage is not None
        assert ElectricityPlans is not None
        assert ElectricityMeterReads is not None

    def test_new_service_imports(self):
        """Test new service imports (gas, broadband) work correctly"""
        from pymercury import (
            GasUsageContent,
            GasUsage,
            BroadbandUsage,
            ServiceUsage
        )

        assert GasUsageContent is not None
        assert GasUsage is not None
        assert BroadbandUsage is not None
        assert ServiceUsage is not None

    def test_exception_imports(self):
        """Test exception classes import correctly"""
        from pymercury import (
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

        # Verify all exception classes are importable
        assert MercuryError is not None
        assert MercuryConfigError is not None
        assert MercuryOAuthError is not None
        assert MercuryAuthenticationError is not None
        assert MercuryAPIError is not None
        assert MercuryAPIConnectionError is not None
        assert MercuryAPIUnauthorizedError is not None
        assert MercuryAPINotFoundError is not None
        assert MercuryAPIRateLimitError is not None

    def test_subpackage_imports(self):
        """Test subpackage imports work correctly"""
        from pymercury.api import MercuryAPIClient, MercuryAPIEndpoints
        from pymercury.oauth import MercuryOAuthClient
        from pymercury.config import MercuryConfig, default_config

        assert MercuryAPIClient is not None
        assert MercuryAPIEndpoints is not None
        assert MercuryOAuthClient is not None
        assert MercuryConfig is not None
        assert default_config is not None

    def test_refactored_models_imports(self):
        """Test that refactored models can be imported from new locations"""
        # Test importing from models package
        from pymercury.api.models import (
            ServiceUsage,
            CustomerInfo,
            Account,
            Service,
            ServiceIds,
            MeterInfo,
            BillSummary,
            ElectricityUsage,
            GasUsage,
            BroadbandUsage
        )

        assert ServiceUsage is not None
        assert CustomerInfo is not None
        assert Account is not None
        assert Service is not None
        assert ServiceIds is not None
        assert MeterInfo is not None
        assert BillSummary is not None
        assert ElectricityUsage is not None
        assert GasUsage is not None
        assert BroadbandUsage is not None

    def test_specific_model_file_imports(self):
        """Test importing from specific model files"""
        from pymercury.api.models.base import ServiceUsage
        from pymercury.api.models.account import CustomerInfo, Account, Service, ServiceIds
        from pymercury.api.models.billing import MeterInfo, BillSummary
        from pymercury.api.models.electricity import ElectricityUsage, ElectricityPlans
        from pymercury.api.models.gas import GasUsage, GasUsageContent
        from pymercury.api.models.broadband import BroadbandUsage

        # Verify all specific imports work
        assert ServiceUsage is not None
        assert CustomerInfo is not None
        assert Account is not None
        assert Service is not None
        assert ServiceIds is not None
        assert MeterInfo is not None
        assert BillSummary is not None
        assert ElectricityUsage is not None
        assert ElectricityPlans is not None
        assert GasUsage is not None
        assert GasUsageContent is not None
        assert BroadbandUsage is not None

    def test_utilities_imports(self):
        """Test utility function imports"""
        from pymercury.utils import (
            generate_pkce_verifier,
            generate_pkce_challenge,
            decode_jwt_payload,
            extract_mercury_ids_from_jwt
        )

        assert generate_pkce_verifier is not None
        assert generate_pkce_challenge is not None
        assert decode_jwt_payload is not None
        assert extract_mercury_ids_from_jwt is not None

    def test_wildcard_imports(self):
        """Test that wildcard imports work (though not recommended)"""
        # This tests the __all__ lists are properly configured
        import pymercury

        # Check that main classes are available via wildcard
        assert hasattr(pymercury, 'MercuryAPIClient')
        assert hasattr(pymercury, 'CustomerInfo')
        assert hasattr(pymercury, 'BroadbandUsage')
        assert hasattr(pymercury, 'ServiceUsage')
        assert hasattr(pymercury, 'MercuryConfig')

    def test_backward_compatibility(self):
        """Test that all old import paths still work"""
        # These should all work exactly as before refactoring
        from pymercury import MercuryAPIClient
        from pymercury.api import CustomerInfo, Account, Service

        # Test that we can create instances
        client = MercuryAPIClient("dummy_token")
        assert client is not None
        assert hasattr(client, 'get_customer_info')
        assert hasattr(client, 'get_electricity_usage')
        assert hasattr(client, 'get_gas_usage')
        assert hasattr(client, 'get_broadband_usage')
