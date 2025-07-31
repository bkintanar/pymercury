#!/usr/bin/env python3
"""
Mercury.co.nz Library Exceptions

Custom exception classes for the Mercury.co.nz library.
"""


class MercuryError(Exception):
    """Base exception for all Mercury.co.nz library errors"""
    pass


class MercuryConfigError(MercuryError):
    """Raised when there's a configuration error"""
    pass


class MercuryOAuthError(MercuryError):
    """Base exception for Mercury.co.nz OAuth authentication errors"""
    pass


class MercuryAuthenticationError(MercuryOAuthError):
    """Raised when authentication credentials are invalid"""
    pass


class MercuryAPIError(MercuryError):
    """Base exception for Mercury.co.nz API errors"""
    pass


class MercuryAPIConnectionError(MercuryAPIError):
    """Raised when API connection fails"""
    pass


class MercuryAPIUnauthorizedError(MercuryAPIError):
    """Raised when API returns 401 Unauthorized"""
    pass


class MercuryAPINotFoundError(MercuryAPIError):
    """Raised when API returns 404 Not Found"""
    pass


class MercuryAPIRateLimitError(MercuryAPIError):
    """Raised when API rate limit is exceeded"""
    pass
