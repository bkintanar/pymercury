#!/usr/bin/env python3
"""
Mercury.co.nz Library Configuration

Configuration management for the Mercury.co.nz library.
"""

import os
from typing import Optional
from .exceptions import MercuryConfigError

# Optional: Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, environment variables must be set manually
    pass


class MercuryConfig:
    """Configuration class for Mercury.co.nz library"""

    def __init__(self,
                 client_id: Optional[str] = None,
                 redirect_uri: Optional[str] = None,
                 base_url: Optional[str] = None,
                 policy: Optional[str] = None,
                 scope: Optional[str] = None,
                 user_agent: Optional[str] = None,
                 timeout: Optional[int] = None,
                 max_redirects: Optional[int] = None,
                 api_base_url: Optional[str] = None,
                 api_subscription_key: Optional[str] = None):
        """
        Initialize Mercury.co.nz configuration

        Args:
            client_id: OAuth client ID (default from env MERCURY_CLIENT_ID)
            redirect_uri: OAuth redirect URI (default from env MERCURY_REDIRECT_URI)
            base_url: OAuth base URL (default from env MERCURY_BASE_URL)
            policy: OAuth policy (default from env MERCURY_POLICY)
            scope: OAuth scope (default from env MERCURY_SCOPE)
            user_agent: HTTP User-Agent (default from env MERCURY_USER_AGENT)
            timeout: Request timeout in seconds (default from env MERCURY_TIMEOUT)
            max_redirects: Maximum redirects (default from env MERCURY_MAX_REDIRECTS)
            api_base_url: API base URL (default from env MERCURY_API_BASE_URL)
            api_subscription_key: API subscription key (default from env MERCURY_API_SUBSCRIPTION_KEY)
        """
        # OAuth Configuration
        self.client_id = client_id or os.getenv(
            'MERCURY_CLIENT_ID',
            "4c8c2c47-24cd-485d-aad9-12f3d95b3ceb"
        )

        self.redirect_uri = redirect_uri or os.getenv(
            'MERCURY_REDIRECT_URI',
            "https://myaccount.mercury.co.nz"
        )

        self.base_url = base_url or os.getenv(
            'MERCURY_BASE_URL',
            "https://login.mercury.co.nz/fc07dca7-cd6a-4578-952b-de7a7afaebdc"
        )

        self.policy = policy or os.getenv(
            'MERCURY_POLICY',
            "b2c_1a_signup_signin"
        )

        self.scope = scope or os.getenv(
            'MERCURY_SCOPE',
            "https://login.mercury.co.nz/aded9884-533e-4081-a4ce-87b0d4e80a45/customer:write "
            "https://login.mercury.co.nz/aded9884-533e-4081-a4ce-87b0d4e80a45/customer:read "
            "openid profile offline_access"
        )

        self.user_agent = user_agent or os.getenv(
            'MERCURY_USER_AGENT',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )

        self.timeout = timeout if timeout is not None else int(os.getenv('MERCURY_TIMEOUT', '20'))
        self.max_redirects = max_redirects if max_redirects is not None else int(os.getenv('MERCURY_MAX_REDIRECTS', '5'))

        # API Configuration
        self.api_base_url = api_base_url or os.getenv(
            'MERCURY_API_BASE_URL',
            'https://apis.mercury.co.nz/selfservice/v1'
        )

        self.api_subscription_key = api_subscription_key or os.getenv(
            'MERCURY_API_SUBSCRIPTION_KEY',
            'f62040b20cf9401fb081880cb71c7dec'
        )

        # Validate required configuration
        self._validate()

    def _validate(self):
        """Validate configuration values"""
        if not self.client_id:
            raise MercuryConfigError("client_id is required")
        if not self.redirect_uri:
            raise MercuryConfigError("redirect_uri is required")
        if not self.base_url:
            raise MercuryConfigError("base_url is required")
        if not self.policy:
            raise MercuryConfigError("policy is required")
        if not self.scope:
            raise MercuryConfigError("scope is required")
        if not self.api_base_url:
            raise MercuryConfigError("api_base_url is required")
        if not self.api_subscription_key:
            raise MercuryConfigError("api_subscription_key is required")
        if self.timeout <= 0:
            raise MercuryConfigError("timeout must be positive")
        if self.max_redirects < 0:
            raise MercuryConfigError("max_redirects must be non-negative")


# Default configuration instance
default_config = MercuryConfig()
