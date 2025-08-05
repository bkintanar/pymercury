#!/usr/bin/env python3
"""
Error handling tests - converted from legacy test_mercury_library.py
"""

import pytest
from pymercury.exceptions import (
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


class TestErrorHandling:
    """Test error handling and exception hierarchy"""

    def test_mercury_error_base(self):
        """Test MercuryError as base exception"""
        try:
            raise MercuryError("Test error")
        except MercuryError as e:
            assert str(e) == "Test error"
            assert isinstance(e, MercuryError)

    def test_mercury_config_error(self):
        """Test MercuryConfigError inheritance"""
        try:
            raise MercuryConfigError("Config error")
        except MercuryError as e:
            assert isinstance(e, MercuryConfigError)
            assert isinstance(e, MercuryError)
            assert str(e) == "Config error"

    def test_mercury_oauth_error(self):
        """Test MercuryOAuthError inheritance"""
        try:
            raise MercuryOAuthError("OAuth error")
        except MercuryError as e:
            assert isinstance(e, MercuryOAuthError)
            assert isinstance(e, MercuryError)
            assert str(e) == "OAuth error"

    def test_mercury_authentication_error(self):
        """Test MercuryAuthenticationError inheritance"""
        try:
            raise MercuryAuthenticationError("Auth error")
        except MercuryError as e:
            assert isinstance(e, MercuryAuthenticationError)
            assert isinstance(e, MercuryError)
            assert str(e) == "Auth error"

    def test_mercury_api_error(self):
        """Test MercuryAPIError inheritance"""
        try:
            raise MercuryAPIError("API error")
        except MercuryError as e:
            assert isinstance(e, MercuryAPIError)
            assert isinstance(e, MercuryError)
            assert str(e) == "API error"

    def test_mercury_api_connection_error(self):
        """Test MercuryAPIConnectionError inheritance"""
        try:
            raise MercuryAPIConnectionError("Connection error")
        except MercuryError as e:
            assert isinstance(e, MercuryAPIConnectionError)
            assert isinstance(e, MercuryAPIError)  # Should inherit from API error
            assert isinstance(e, MercuryError)
            assert str(e) == "Connection error"

    def test_mercury_api_unauthorized_error(self):
        """Test MercuryAPIUnauthorizedError inheritance"""
        try:
            raise MercuryAPIUnauthorizedError("Unauthorized error")
        except MercuryError as e:
            assert isinstance(e, MercuryAPIUnauthorizedError)
            assert isinstance(e, MercuryAPIError)  # Should inherit from API error
            assert isinstance(e, MercuryError)
            assert str(e) == "Unauthorized error"

    def test_mercury_api_not_found_error(self):
        """Test MercuryAPINotFoundError inheritance"""
        try:
            raise MercuryAPINotFoundError("Not found error")
        except MercuryError as e:
            assert isinstance(e, MercuryAPINotFoundError)
            assert isinstance(e, MercuryAPIError)  # Should inherit from API error
            assert isinstance(e, MercuryError)
            assert str(e) == "Not found error"

    def test_mercury_api_rate_limit_error(self):
        """Test MercuryAPIRateLimitError inheritance"""
        try:
            raise MercuryAPIRateLimitError("Rate limit error")
        except MercuryError as e:
            assert isinstance(e, MercuryAPIRateLimitError)
            assert isinstance(e, MercuryAPIError)  # Should inherit from API error
            assert isinstance(e, MercuryError)
            assert str(e) == "Rate limit error"

    def test_exception_hierarchy(self):
        """Test complete exception hierarchy"""
        # Test that all API errors inherit properly
        api_exceptions = [
            MercuryAPIError,
            MercuryAPIConnectionError,
            MercuryAPIUnauthorizedError,
            MercuryAPINotFoundError,
            MercuryAPIRateLimitError
        ]

        for exc_class in api_exceptions:
            exception = exc_class("Test message")
            assert isinstance(exception, MercuryError)
            assert isinstance(exception, MercuryAPIError)

    def test_exception_with_additional_data(self):
        """Test exceptions can carry additional data"""
        # Test with status code
        api_error = MercuryAPIError("API failed with status 500")
        assert "500" in str(api_error)

        # Test with detailed message
        auth_error = MercuryAuthenticationError("Invalid credentials: check email and password")
        assert "Invalid credentials" in str(auth_error)
        assert "email and password" in str(auth_error)

    def test_exception_catching_patterns(self):
        """Test different exception catching patterns"""

        # Test catching specific exception
        with pytest.raises(MercuryAPIConnectionError):
            raise MercuryAPIConnectionError("Connection failed")

        # Test catching by parent class
        with pytest.raises(MercuryAPIError):
            raise MercuryAPIUnauthorizedError("Unauthorized")

        # Test catching by base class
        with pytest.raises(MercuryError):
            raise MercuryConfigError("Config issue")

    def test_error_message_formatting(self):
        """Test that error messages are properly formatted"""
        errors = [
            (MercuryError, "Base error message"),
            (MercuryConfigError, "Configuration validation failed"),
            (MercuryOAuthError, "OAuth flow interrupted"),
            (MercuryAuthenticationError, "Authentication credentials invalid"),
            (MercuryAPIError, "API request failed"),
            (MercuryAPIConnectionError, "Unable to connect to API"),
            (MercuryAPIUnauthorizedError, "API access denied"),
            (MercuryAPINotFoundError, "API endpoint not found"),
            (MercuryAPIRateLimitError, "API rate limit exceeded")
        ]

        for exc_class, message in errors:
            exception = exc_class(message)
            assert str(exception) == message
            assert len(str(exception)) > 0

    def test_exception_chaining(self):
        """Test exception chaining for debugging"""
        original_error = ValueError("Original problem")

        try:
            try:
                raise original_error
            except ValueError as e:
                raise MercuryAPIError("API failed due to validation") from e
        except MercuryAPIError as api_error:
            assert api_error.__cause__ is original_error
            assert isinstance(api_error.__cause__, ValueError)

    def test_empty_error_messages(self):
        """Test exceptions with empty or None messages"""
        # Test with empty string
        error1 = MercuryError("")
        assert str(error1) == ""

        # Test with None (should convert to string)
        error2 = MercuryError(None)
        assert str(error2) == "None"

    def test_exception_instantiation_without_message(self):
        """Test that exceptions can be created without messages"""
        error = MercuryError()
        assert isinstance(error, MercuryError)
        # Should not raise an error when converted to string
        str(error)
