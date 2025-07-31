#!/usr/bin/env python3
"""
Mercury.co.nz Main Client

Combined OAuth and API client for Mercury.co.nz providing a simple interface
for complete Mercury.co.nz integration.
"""

from typing import Optional, List, Dict, Any

from .config import MercuryConfig, default_config
from .exceptions import MercuryError, MercuryOAuthError
from .oauth import MercuryOAuthClient, OAuthTokens
from .api import MercuryAPIClient, CustomerInfo, Account, Service, ServiceIds


class CompleteAccountData:
    """Container for complete Mercury.co.nz account data"""

    def __init__(self,
                 tokens: OAuthTokens,
                 customer_info: Optional[CustomerInfo],
                 accounts: List[Account],
                 services: List[Service],
                 service_ids: ServiceIds):
        self.tokens = tokens
        self.customer_info = customer_info
        self.accounts = accounts
        self.services = services
        self.service_ids = service_ids

    @property
    def customer_id(self) -> Optional[str]:
        """Get customer ID"""
        return self.tokens.customer_id

    @property
    def account_ids(self) -> List[str]:
        """Get list of account IDs"""
        return [account.account_id for account in self.accounts if account.account_id]

    @property
    def access_token(self) -> Optional[str]:
        """Get OAuth access token"""
        return self.tokens.access_token

    @property
    def email(self) -> Optional[str]:
        """Get user email"""
        return self.tokens.email

    @property
    def name(self) -> Optional[str]:
        """Get user name"""
        return self.tokens.name


class MercuryClient:
    """
    Main Mercury.co.nz Client

    Combines OAuth authentication and API functionality to provide a simple
    interface for complete Mercury.co.nz integration.

    Example:
        client = MercuryClient(email, password)
        client.login()

        # Easy access to IDs
        customer_id = client.customer_id
        account_ids = client.account_ids
        electricity_services = client.service_ids.electricity

        # Get complete data
        data = client.get_complete_account_data()
    """

    def __init__(self, email: str, password: str, config: Optional[MercuryConfig] = None, verbose: bool = False):
        """
        Initialize the Mercury.co.nz client

        Args:
            email: Mercury.co.nz account email address
            password: Mercury.co.nz account password
            config: Configuration object (uses default if None)
            verbose: Enable verbose logging output
        """
        self._email = email
        self._password = password
        self.config = config or default_config
        self.verbose = verbose

        # Initialize OAuth client
        self.oauth_client = MercuryOAuthClient(email, password, config, verbose)

        # These will be set after login
        self._tokens: Optional[OAuthTokens] = None
        self._api_client: Optional[MercuryAPIClient] = None
        self._customer_info: Optional[CustomerInfo] = None
        self._accounts: List[Account] = []
        self._services: List[Service] = []
        self._service_ids: Optional[ServiceIds] = None

    def _log(self, message: str):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            print(message)

    def login(self) -> OAuthTokens:
        """
        Perform OAuth login and initialize API client

        Returns:
            OAuthTokens object containing access tokens and user information

        Raises:
            MercuryAuthenticationError: If credentials are invalid
            MercuryOAuthError: If OAuth flow fails
        """
        self._log("🔄 Logging into Mercury.co.nz...")

        # Perform OAuth authentication
        self._tokens = self.oauth_client.authenticate()

        if not self._tokens.access_token:
            raise MercuryOAuthError("Failed to obtain access token")

        # Initialize API client with access token
        self._api_client = MercuryAPIClient(self._tokens.access_token, self.config, self.verbose)

        self._log("✅ Mercury.co.nz login successful!")
        return self._tokens

    def smart_login(self, existing_tokens: Optional[OAuthTokens] = None) -> OAuthTokens:
        """
        Smart login that uses refresh token if available, otherwise performs full login

        Args:
            existing_tokens: Previously saved tokens to attempt refresh with

        Returns:
            Valid OAuthTokens object
        """
        self._log("🔄 Smart login: checking for refresh opportunities...")

        # Use the OAuth client's smart login method
        self._tokens = self.oauth_client.login_or_refresh(self._email, self._password, existing_tokens)

        # Initialize/update API client with new access token
        self._api_client = MercuryAPIClient(self._tokens.access_token, self.config, self.verbose)

        self._log("✅ Smart login successful!")
        return self._tokens

    def refresh_if_needed(self) -> bool:
        """
        Automatically refresh tokens if they are expired or expiring soon

        Returns:
            True if tokens were refreshed, False if no refresh was needed/possible
        """
        if not self._tokens:
            return False

        if self._tokens.expires_soon() and self._tokens.has_refresh_token():
            self._log("🔄 Tokens expiring soon, attempting automatic refresh...")
            refreshed_tokens = self.oauth_client.refresh_tokens(self._tokens.refresh_token)

            if refreshed_tokens:
                self._tokens = refreshed_tokens
                # Update API client with new access token
                self._api_client = MercuryAPIClient(self._tokens.access_token, self.config, self.verbose)
                self._log("✅ Tokens automatically refreshed!")
                return True
            else:
                self._log("⚠️ Automatic token refresh failed")

        return False

    def _ensure_logged_in(self):
        """Ensure the client is logged in with valid tokens"""
        if not self._tokens or not self._api_client:
            raise MercuryError("Must call login() first")

        # Auto-refresh if tokens are expired/expiring soon
        if self._tokens.is_expired():
            if self._tokens.has_refresh_token():
                self._log("🔄 Tokens expired, attempting automatic refresh...")
                refreshed_tokens = self.oauth_client.refresh_tokens(self._tokens.refresh_token)
                if refreshed_tokens:
                    self._tokens = refreshed_tokens
                    self._api_client = MercuryAPIClient(self._tokens.access_token, self.config, self.verbose)
                    self._log("✅ Tokens automatically refreshed!")
                else:
                    raise MercuryError("Tokens expired and refresh failed. Please call login() again.")
            else:
                raise MercuryError("Tokens expired and no refresh token available. Please call login() again.")
        elif self._tokens.expires_soon():
            self.refresh_if_needed()  # Try to refresh proactively

    def get_complete_account_data(self) -> CompleteAccountData:
        """
        Get complete account data including all customer information,
        accounts, and services

        Returns:
            CompleteAccountData object with all Mercury.co.nz account information

        Raises:
            MercuryError: If not logged in or API calls fail
        """
        self._ensure_logged_in()

        self._log("🚀 Getting complete Mercury.co.nz account data...")

        customer_id = self._tokens.customer_id
        if not customer_id:
            raise MercuryError("Customer ID not found in tokens")

        # Get customer info
        self._customer_info = self._api_client.get_customer_info(customer_id)

        # Get accounts
        self._accounts = self._api_client.get_accounts(customer_id)
        if not self._accounts:
            raise MercuryError("No customer accounts found")

        # Get all services
        account_ids = [account.account_id for account in self._accounts if account.account_id]
        self._services = self._api_client.get_all_services(customer_id, account_ids)

        # Organize service IDs
        self._service_ids = ServiceIds(self._services)

        complete_data = CompleteAccountData(
            tokens=self._tokens,
            customer_info=self._customer_info,
            accounts=self._accounts,
            services=self._services,
            service_ids=self._service_ids
        )

        self._log("✅ Complete account data retrieved successfully!")
        self._log(f"   🆔 Customer ID: {customer_id}")
        self._log(f"   🏦 Account IDs: {account_ids}")
        self._log(f"   🔧 Service IDs: {len(self._service_ids.all)} total")

        return complete_data

    # Properties for easy access to common data
    @property
    def is_logged_in(self) -> bool:
        """Check if client is logged in"""
        return self._tokens is not None and self._api_client is not None

    @property
    def customer_id(self) -> Optional[str]:
        """Get customer ID (requires login)"""
        return self._tokens.customer_id if self._tokens else None

    @property
    def account_ids(self) -> List[str]:
        """Get account IDs (requires get_complete_account_data)"""
        return [account.account_id for account in self._accounts if account.account_id]

    @property
    def service_ids(self) -> Optional[ServiceIds]:
        """Get organized service IDs (requires get_complete_account_data)"""
        return self._service_ids

    @property
    def access_token(self) -> Optional[str]:
        """Get OAuth access token (requires login)"""
        return self._tokens.access_token if self._tokens else None

    @property
    def email(self) -> Optional[str]:
        """Get user email (requires login)"""
        return self._tokens.email if self._tokens else None

    @property
    def name(self) -> Optional[str]:
        """Get user name (requires login)"""
        return self._tokens.name if self._tokens else None

    # Direct access to underlying clients for advanced usage
    @property
    def oauth(self) -> MercuryOAuthClient:
        """Get OAuth client for advanced OAuth operations"""
        return self.oauth_client

    @property
    def api(self) -> Optional[MercuryAPIClient]:
        """Get API client for direct API operations (requires login)"""
        return self._api_client

    def save_tokens(self) -> Dict[str, Any]:
        """
        Save current tokens to a dictionary for persistence

        Returns:
            Dictionary containing token data that can be saved to file/database
        """
        if not self._tokens:
            return {}

        return {
            'access_token': self._tokens.access_token,
            'refresh_token': self._tokens.refresh_token,
            'expires_in': self._tokens.expires_in,
            'token_type': self._tokens.token_type,
            'expires_at': self._tokens.expires_at.isoformat() if self._tokens.expires_at else None,
            'customer_id': self._tokens.customer_id,
            'email': self._tokens.email,
            'name': self._tokens.name
        }

    def load_tokens(self, token_data: Dict[str, Any]) -> bool:
        """
        Load tokens from saved data

        Args:
            token_data: Dictionary containing saved token data

        Returns:
            True if tokens were loaded successfully and are still valid
        """
        try:
            # Reconstruct tokens object
            self._tokens = OAuthTokens(token_data)

            # Check if tokens are still valid
            if self._tokens.is_expired():
                if self._tokens.has_refresh_token():
                    # Try to refresh expired tokens
                    refreshed = self.oauth_client.refresh_tokens(self._tokens.refresh_token)
                    if refreshed:
                        self._tokens = refreshed
                    else:
                        return False
                else:
                    return False

            # Initialize API client if tokens are valid
            if self._tokens.access_token:
                self._api_client = MercuryAPIClient(self._tokens.access_token, self.config, self.verbose)
                return True

        except Exception as e:
            self._log(f"⚠️ Error loading tokens: {e}")

        return False

    def login_with_saved_tokens(self, token_data: Optional[Dict[str, Any]] = None) -> OAuthTokens:
        """
        Convenience method to login using saved tokens with automatic fallback

        Args:
            token_data: Previously saved token data (optional)

        Returns:
            Valid OAuthTokens object
        """
        # Try to load saved tokens first
        if token_data and self.load_tokens(token_data):
            self._log("✅ Successfully logged in using saved tokens!")
            return self._tokens

        # Fall back to smart login
        existing_tokens = OAuthTokens(token_data) if token_data else None
        return self.smart_login(existing_tokens)


# Convenience functions for simple usage
def authenticate(email: str, password: str, config: Optional[MercuryConfig] = None, verbose: bool = False) -> OAuthTokens:
    """
    Convenience function to perform Mercury.co.nz OAuth authentication

    Args:
        email: Mercury.co.nz account email
        password: Mercury.co.nz account password
        config: Configuration object (uses default if None)
        verbose: Enable verbose logging

    Returns:
        OAuthTokens object containing access tokens and user information
    """
    client = MercuryClient(email, password, config, verbose)
    return client.login()


def get_complete_data(email: str, password: str, config: Optional[MercuryConfig] = None, verbose: bool = False) -> CompleteAccountData:
    """
    Convenience function to get complete Mercury.co.nz account data

    Args:
        email: Mercury.co.nz account email
        password: Mercury.co.nz account password
        config: Configuration object (uses default if None)
        verbose: Enable verbose logging

    Returns:
        CompleteAccountData object with all account information
    """
    client = MercuryClient(email, password, config, verbose)
    client.login()
    return client.get_complete_account_data()
