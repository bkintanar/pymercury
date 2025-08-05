#!/usr/bin/env python3
"""
Utility function tests - converted from legacy test_mercury_library.py
"""

import pytest
from pymercury.utils import (
    generate_pkce_verifier,
    generate_pkce_challenge,
    decode_jwt_payload,
    extract_mercury_ids_from_jwt
)


class TestUtilities:
    """Test utility functions"""

    def test_pkce_verifier_generation(self):
        """Test PKCE verifier generation"""
        verifier = generate_pkce_verifier()

        # Should be a string
        assert isinstance(verifier, str)

        # Should be appropriate length (typically 43-128 characters)
        assert 43 <= len(verifier) <= 128

        # Should contain only URL-safe characters
        import string
        allowed_chars = string.ascii_letters + string.digits + '-._~'
        assert all(c in allowed_chars for c in verifier)

        # Multiple calls should generate different verifiers
        verifier2 = generate_pkce_verifier()
        assert verifier != verifier2

    def test_pkce_challenge_generation(self):
        """Test PKCE challenge generation from verifier"""
        verifier = generate_pkce_verifier()
        challenge = generate_pkce_challenge(verifier)

        # Should be a string
        assert isinstance(challenge, str)

        # Should be base64 URL-encoded (43 characters for SHA256)
        assert len(challenge) == 43

        # Should end without padding (URL-safe base64)
        assert not challenge.endswith('=')

        # Same verifier should always produce same challenge
        challenge2 = generate_pkce_challenge(verifier)
        assert challenge == challenge2

        # Different verifiers should produce different challenges
        different_verifier = generate_pkce_verifier()
        different_challenge = generate_pkce_challenge(different_verifier)
        assert challenge != different_challenge

    def test_pkce_verifier_length_variations(self):
        """Test PKCE verifier with different lengths"""
        # Test multiple generations
        verifiers = [generate_pkce_verifier() for _ in range(10)]

        # All should be valid length
        for verifier in verifiers:
            assert 43 <= len(verifier) <= 128

        # All should be unique
        assert len(set(verifiers)) == len(verifiers)

    def test_pkce_challenge_deterministic(self):
        """Test that PKCE challenge is deterministic"""
        test_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

        challenge1 = generate_pkce_challenge(test_verifier)
        challenge2 = generate_pkce_challenge(test_verifier)

        assert challenge1 == challenge2
        assert len(challenge1) == 43

    def test_jwt_payload_decoding(self):
        """Test JWT payload decoding"""
        # Mock JWT payload (base64 encoded JSON)
        import base64
        import json

        payload_data = {
            'sub': '123456',
            'email': 'test@example.com',
            'extension_customerId': '7334151',
            'given_name': 'Test',
            'family_name': 'User',
            'exp': 1640995200
        }

        # Encode as JWT payload (base64)
        payload_json = json.dumps(payload_data)
        payload_bytes = payload_json.encode('utf-8')
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8')

        # Remove padding if present (JWT style)
        payload_b64 = payload_b64.rstrip('=')

        # Create a valid JWT format: header.payload.signature
        import json
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        signature = "fake_signature"
        jwt_token = f"{header_b64}.{payload_b64}.{signature}"

        # Test decoding
        decoded = decode_jwt_payload(jwt_token)

        assert decoded is not None
        assert decoded['sub'] == '123456'
        assert decoded['email'] == 'test@example.com'
        assert decoded['extension_customerId'] == '7334151'
        assert decoded['given_name'] == 'Test'
        assert decoded['family_name'] == 'User'

    def test_extract_mercury_ids_from_jwt(self):
        """Test Mercury ID extraction from JWT claims"""
        # Test with complete claims
        sample_claims = {
            'extension_customerId': '7334151',
            'email': 'test@example.com',
            'given_name': 'Test',
            'family_name': 'User',
            'sub': 'subject_id'
        }

        extracted = extract_mercury_ids_from_jwt(sample_claims)

        assert extracted['customerId'] == '7334151'
        assert extracted['email'] == 'test@example.com'
        assert extracted['given_name'] == 'Test'
        assert extracted['family_name'] == 'User'

    def test_extract_mercury_ids_missing_customer_id(self):
        """Test Mercury ID extraction when customer ID is missing"""
        claims_without_customer_id = {
            'email': 'test@example.com',
            'given_name': 'Test',
            'family_name': 'User'
        }

        extracted = extract_mercury_ids_from_jwt(claims_without_customer_id)

        # Should still extract other fields
        assert extracted['email'] == 'test@example.com'
        assert extracted['given_name'] == 'Test'
        assert extracted['family_name'] == 'User'

        # Customer ID should be None or not present
        assert extracted.get('customerId') is None

    def test_extract_mercury_ids_alternative_formats(self):
        """Test Mercury ID extraction with alternative field formats"""
        # Test with different possible field names
        alternative_claims = {
            'extension_customerId': '1234567',
            'customer_id': '7654321',  # Alternative format
            'email': 'alt@example.com'
        }

        extracted = extract_mercury_ids_from_jwt(alternative_claims)

        # Should prefer extension_customerId if present
        assert extracted['customerId'] == '1234567'
        assert extracted['email'] == 'alt@example.com'

    def test_jwt_decoding_edge_cases(self):
        """Test JWT decoding with edge cases"""
        import base64
        import json

        # Test with minimal payload
        minimal_payload = {'sub': 'test'}
        payload_json = json.dumps(minimal_payload)
        payload_bytes = payload_json.encode('utf-8')
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')

        # Create valid JWT format
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        jwt_token = f"{header_b64}.{payload_b64}.fake_signature"

        decoded = decode_jwt_payload(jwt_token)
        assert decoded is not None
        assert decoded['sub'] == 'test'

        # Test with empty payload
        empty_payload = {}
        payload_json = json.dumps(empty_payload)
        payload_bytes = payload_json.encode('utf-8')
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
        jwt_token_empty = f"{header_b64}.{payload_b64}.fake_signature"

        decoded = decode_jwt_payload(jwt_token_empty)
        assert decoded is not None
        assert decoded == {}

    def test_mercury_id_extraction_with_numeric_ids(self):
        """Test Mercury ID extraction with numeric customer IDs"""
        claims_with_numeric = {
            'extension_customerId': 7334151,  # Numeric instead of string
            'email': 'numeric@example.com'
        }

        extracted = extract_mercury_ids_from_jwt(claims_with_numeric)

        # Should handle numeric IDs (convert to string if needed)
        customer_id = extracted['customerId']
        assert str(customer_id) == '7334151'
        assert extracted['email'] == 'numeric@example.com'

    def test_utility_function_error_handling(self):
        """Test that utility functions handle errors gracefully"""
        # Test PKCE challenge with invalid verifier
        try:
            challenge = generate_pkce_challenge("")
            # Should either work or raise appropriate error
            assert isinstance(challenge, str) or challenge is None
        except Exception as e:
            # Should be a reasonable error type
            assert isinstance(e, (ValueError, TypeError))

        # Test JWT decoding with invalid base64
        try:
            decoded = decode_jwt_payload("invalid_base64!")
            # Should either work or raise appropriate error
            assert decoded is None or isinstance(decoded, dict)
        except Exception as e:
            # Should be a reasonable error type
            assert isinstance(e, (ValueError, TypeError))

    def test_utility_functions_exist(self):
        """Test that all expected utility functions exist and are callable"""
        functions = [
            generate_pkce_verifier,
            generate_pkce_challenge,
            decode_jwt_payload,
            extract_mercury_ids_from_jwt
        ]

        for func in functions:
            assert callable(func), f"Function {func.__name__} is not callable"

    def test_pkce_flow_integration(self):
        """Test complete PKCE flow integration"""
        # Generate verifier
        verifier = generate_pkce_verifier()
        assert len(verifier) >= 43

        # Generate challenge
        challenge = generate_pkce_challenge(verifier)
        assert len(challenge) == 43

        # Verify they're related (challenge is hash of verifier)
        import hashlib
        import base64

        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        assert challenge == expected_challenge
