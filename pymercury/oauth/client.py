#!/usr/bin/env python3
"""
Mercury.co.nz OAuth Client

OAuth 2.0 PKCE authentication client for Mercury.co.nz
"""

import requests
import re
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse

from ..config import MercuryConfig, default_config
from ..exceptions import MercuryOAuthError, MercuryAuthenticationError
from ..utils import (
    generate_pkce_verifier,
    generate_pkce_challenge,
    extract_from_html,
    parse_mercury_json,
    extract_auth_code_from_url,
    decode_jwt_payload,
    extract_mercury_ids_from_jwt
)


class OAuthTokens:
    """Container for OAuth tokens and user information"""

    def __init__(self, token_data: Dict[str, Any]):
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.expires_in = token_data.get('expires_in')  # seconds until expiration
        self.token_type = token_data.get('token_type', 'Bearer')

        # Calculate expiration time
        if self.expires_in:
            self.expires_at = datetime.now() + timedelta(seconds=int(self.expires_in))
        else:
            self.expires_at = None

        # Extract user information from JWT
        if self.access_token:
            jwt_claims = decode_jwt_payload(self.access_token)
            if jwt_claims:
                user_info = extract_mercury_ids_from_jwt(jwt_claims)
                for key, value in user_info.items():
                    # Use internal attribute names to avoid property conflicts
                    setattr(self, f'_{key}', value)

    @property
    def customer_id(self) -> Optional[str]:
        """Get customer ID"""
        return getattr(self, '_customerId', None)

    @property
    def account_id(self) -> Optional[str]:
        """Get account ID"""
        return getattr(self, '_accountId', None)

    @property
    def service_id(self) -> Optional[str]:
        """Get service ID"""
        return getattr(self, '_serviceId', None)

    @property
    def email(self) -> Optional[str]:
        """Get user email"""
        return getattr(self, '_email', None)

    @property
    def name(self) -> Optional[str]:
        """Get user full name"""
        given_name = getattr(self, '_given_name', '')
        family_name = getattr(self, '_family_name', '')
        return ' '.join(filter(None, [given_name, family_name])) or None

    def is_expired(self) -> bool:
        """Check if the access token is expired"""
        if not self.expires_at:
            return False  # If no expiration time, assume not expired
        return datetime.now() >= self.expires_at

    def expires_soon(self, buffer_minutes: int = 5) -> bool:
        """Check if the access token expires within the buffer time"""
        if not self.expires_at:
            return False
        buffer = timedelta(minutes=buffer_minutes)
        return datetime.now() + buffer >= self.expires_at

    def has_refresh_token(self) -> bool:
        """Check if a refresh token is available"""
        return bool(self.refresh_token)

    def time_until_expiry(self) -> Optional[timedelta]:
        """Get time remaining until token expires"""
        if not self.expires_at:
            return None
        return self.expires_at - datetime.now()


class MercuryOAuthClient:
    """
    Mercury.co.nz OAuth 2.0 PKCE Authentication Client

    Handles the complete OAuth 2.0 PKCE flow for Mercury.co.nz,
    including Azure B2C authentication and token exchange.
    """

    def __init__(self, email: str, password: str, config: Optional[MercuryConfig] = None, verbose: bool = False):
        """
        Initialize the Mercury.co.nz OAuth client

        Args:
            email: Mercury.co.nz account email address
            password: Mercury.co.nz account password
            config: Configuration object (uses default if None)
            verbose: Enable verbose logging output
        """
        self.email = email
        self.password = password
        self.config = config or default_config
        self.verbose = verbose

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.config.user_agent})

        # Generate PKCE parameters
        self.code_verifier = generate_pkce_verifier()
        self.code_challenge = generate_pkce_challenge(self.code_verifier)
        self.state = f"state_{secrets.token_urlsafe(16)}"
        self.nonce = f"nonce_{secrets.token_urlsafe(16)}"

    def _log(self, message: str):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            print(message)

    def authenticate(self) -> OAuthTokens:
        """
        Perform complete OAuth authentication flow

        Returns:
            OAuthTokens object containing access tokens and user information

        Raises:
            MercuryAuthenticationError: If credentials are invalid
            MercuryOAuthError: If OAuth flow fails for other reasons
        """
        self._log("🔄 Starting Mercury.co.nz OAuth authentication...")

        # Step 1: Get initial auth page and transaction data
        self._log("Step 1: Getting authorization page and initial transaction data...")
        auth_url_base = f"{self.config.base_url}/{self.config.policy}/oauth2/v2.0/authorize"

        initial_auth_params = {
            'client_id': self.config.client_id,
            'scope': self.config.scope,
            'redirect_uri': self.config.redirect_uri,
            'response_type': 'code',
            'code_challenge_method': 'S256',
            'code_challenge': self.code_challenge,
            'state': self.state,
            'nonce': self.nonce
        }

        auth_page_response = self.session.get(auth_url_base, params=initial_auth_params)
        auth_page_response.raise_for_status()

        # Extract CSRF token and transaction ID
        csrf_token = extract_from_html(auth_page_response.text, r'"csrf":"([^"]*)"')
        trans_id = extract_from_html(auth_page_response.text, r'"transId":"([^"]*)"')

        # Step 2: Submit credentials
        self._log("Step 2: Submitting credentials...")
        login_post_url = f"{self.config.base_url}/{self.config.policy}/SelfAsserted"
        login_params = {'tx': trans_id, 'p': self.config.policy}
        login_data = {
            'request_type': 'RESPONSE',
            'signInName': self.email,
            'password': self.password
        }

        login_headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-CSRF-TOKEN': csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': auth_page_response.url,
            'Origin': f"{urlparse(auth_page_response.url).scheme}://{urlparse(auth_page_response.url).netloc}"
        }

        login_response = self.session.post(login_post_url, params=login_params, data=login_data, headers=login_headers)
        login_response.raise_for_status()

        login_result = parse_mercury_json(login_response.text)
        if not login_result or login_result.get('status') != '200':
            raise MercuryAuthenticationError(f"Login failed. Server responded with: {login_response.text}")

        self._log("✅ Credentials accepted. Session is authenticated.")

        # Step 3: Complete Mercury.co.nz B2C authorization
        self._log("Step 3: Completing Mercury.co.nz B2C authorization...")
        tokens = self._mercury_b2c_fresh_flow()
        if tokens:
            return tokens

        raise MercuryOAuthError("Could not complete Mercury.co.nz B2C authentication flow")

    def _mercury_b2c_fresh_flow(self) -> Optional[OAuthTokens]:
        """Mercury.co.nz B2C fresh flow - the working approach"""
        self._log("🔄 Starting Mercury.co.nz B2C fresh flow...")

        # Create fresh session and copy authenticated cookies
        fresh_session, fresh_verifier, fresh_challenge, fresh_state, fresh_nonce = self._generate_fresh_session()

        for cookie in self.session.cookies:
            fresh_session.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)

        # Get Mercury.co.nz B2C authorization page
        auth_url_base = f"{self.config.base_url}/{self.config.policy}/oauth2/v2.0/authorize"
        auth_params = {
            'client_id': self.config.client_id,
            'scope': self.config.scope,
            'redirect_uri': self.config.redirect_uri,
            'response_type': 'code',
            'code_challenge_method': 'S256',
            'code_challenge': fresh_challenge,
            'state': fresh_state,
            'nonce': fresh_nonce,
            'response_mode': 'query',
            'ui_locales': 'en-US'
        }

        mercury_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache'
        }

        mercury_response = fresh_session.get(auth_url_base, params=auth_params,
                                           headers=mercury_headers, timeout=self.config.timeout)

        if mercury_response.status_code == 200:
            return self._extract_and_use_mercury_settings(fresh_session, mercury_response.text, fresh_verifier)

        return None

    def _generate_fresh_session(self):
        """Generate a fresh session for Mercury.co.nz B2C flow"""
        fresh_session = requests.Session()
        fresh_session.headers.update({'User-Agent': self.config.user_agent})

        # Generate fresh PKCE parameters
        fresh_verifier = generate_pkce_verifier()
        fresh_challenge = generate_pkce_challenge(fresh_verifier)
        fresh_state = f"state_{secrets.token_urlsafe(16)}"
        fresh_nonce = f"nonce_{secrets.token_urlsafe(16)}"

        return fresh_session, fresh_verifier, fresh_challenge, fresh_state, fresh_nonce

    def _extract_and_use_mercury_settings(self, session: requests.Session, response_text: str, verifier: str) -> Optional[OAuthTokens]:
        """Extract SETTINGS from Mercury.co.nz response and complete authentication"""
        self._log("  🔧 Extracting Mercury.co.nz B2C settings...")

        try:
            # Extract SETTINGS object from HTML
            settings_match = re.search(r'var SETTINGS = ({[^;]+});', response_text, re.DOTALL)
            if not settings_match:
                self._log("  ❌ Could not find SETTINGS object")
                return None

            settings = json.loads(settings_match.group(1))
            self._log("  ✅ Successfully extracted SETTINGS object")

            csrf_token = settings.get('csrf')
            trans_id = settings.get('transId')

            if not csrf_token or not trans_id:
                self._log("  ❌ Missing required tokens in SETTINGS")
                return None

            return self._mercury_combined_signin_post(session, csrf_token, trans_id, verifier)

        except (json.JSONDecodeError, Exception) as e:
            self._log(f"  ❌ Error extracting settings: {e}")
            return None

    def _mercury_combined_signin_post(self, session: requests.Session, csrf_token: str, trans_id: str, verifier: str) -> Optional[OAuthTokens]:
        """Use Mercury's CombinedSigninAndSignup POST endpoint"""
        self._log("  🎯 Using Mercury.co.nz CombinedSigninAndSignup POST endpoint...")

        try:
            # First authenticate on the fresh session
            auth_url = f"{self.config.base_url}/{self.config.policy}/SelfAsserted"
            auth_params = {'tx': trans_id, 'p': self.config.policy}
            auth_data = {
                'request_type': 'RESPONSE',
                'signInName': self.email,
                'password': self.password
            }

            auth_headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest'
            }

            auth_response = session.post(auth_url, params=auth_params, data=auth_data, headers=auth_headers)

            if auth_response.status_code != 200:
                self._log(f"  ❌ Fresh session auth failed with status: {auth_response.status_code}")
                return None

            auth_result = parse_mercury_json(auth_response.text)
            if not auth_result or auth_result.get('status') != '200':
                self._log(f"  ❌ Fresh session auth failed: {auth_result}")
                return None

            self._log("  ✅ Fresh session authenticated successfully")

            # Now use the CombinedSigninAndSignup endpoint
            combined_url = f"{self.config.base_url}/{self.config.policy}/api/CombinedSigninAndSignup/confirmed"

            combined_data = {
                'request_type': 'RESPONSE',
                'signInName': self.email,
                'password': self.password,
                'rememberMe': 'false'
            }

            combined_params = {'tx': trans_id, 'p': self.config.policy}

            combined_headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }

            combined_response = session.post(combined_url, params=combined_params, data=combined_data,
                                           headers=combined_headers, allow_redirects=False, timeout=self.config.timeout)

            self._log(f"  📨 CombinedSigninAndSignup response: {combined_response.status_code}")

            if combined_response.status_code in [302, 303, 307, 308]:
                self._log("  🎉 Got authorization redirect!")
                auth_code = self._follow_redirects_for_code(combined_response)
                tokens = self._exchange_code_for_token(auth_code, verifier)

                return tokens

        except Exception as e:
            self._log(f"  ❌ Error in CombinedSigninAndSignup POST: {e}")

        return None

    def _follow_redirects_for_code(self, response: requests.Response) -> str:
        """Follow redirects to find authorization code"""
        current_response = response

        for i in range(self.config.max_redirects):
            # Check current URL for auth code
            if auth_code := extract_auth_code_from_url(current_response.url or ""):
                self._log("✅ Authorization code found!")
                return auth_code

            # Check if there's a redirect
            if 'Location' not in current_response.headers:
                break

            location = current_response.headers['Location']

            # Check redirect URL for auth code
            if auth_code := extract_auth_code_from_url(location):
                self._log("✅ Authorization code found!")
                return auth_code

            # Follow the redirect
            next_url = location if location.startswith('http') else urljoin(current_response.url, location)

            try:
                current_response = self.session.get(next_url, allow_redirects=False, timeout=10)
            except Exception:
                break

        raise MercuryOAuthError("Could not find authorization code in redirects")

    def _exchange_code_for_token(self, auth_code: str, code_verifier: str) -> OAuthTokens:
        """Exchange authorization code for tokens"""
        self._log("Step 4: Exchanging authorization code for tokens...")
        token_url = f"{self.config.base_url}/{self.config.policy}/oauth2/v2.0/token"

        token_data = {
            'grant_type': 'authorization_code',
            'client_id': self.config.client_id,
            'scope': self.config.scope,
            'code': auth_code,
            'redirect_uri': self.config.redirect_uri,
            'code_verifier': code_verifier,
        }

        token_response = self.session.post(token_url, data=token_data)

        if token_response.status_code != 200:
            token_response.raise_for_status()

        self._log("✅ Tokens exchanged successfully.")
        tokens_data = token_response.json()

        return OAuthTokens(tokens_data)

    def refresh_tokens(self, refresh_token: str) -> Optional[OAuthTokens]:
        """Refresh access token using refresh token

        Args:
            refresh_token: The refresh token to use for getting new access token

        Returns:
            New OAuthTokens object with refreshed tokens, or None if refresh failed
        """
        self._log("🔄 Refreshing access token using refresh token...")
        token_url = f"{self.config.base_url}/{self.config.policy}/oauth2/v2.0/token"

        refresh_data = {
            'grant_type': 'refresh_token',
            'client_id': self.config.client_id,
            'scope': self.config.scope,
            'refresh_token': refresh_token,
        }

        try:
            refresh_response = self.session.post(token_url, data=refresh_data)

            if refresh_response.status_code == 200:
                self._log("✅ Tokens refreshed successfully.")
                tokens_data = refresh_response.json()
                return OAuthTokens(tokens_data)
            else:
                self._log(f"⚠️ Token refresh failed with status {refresh_response.status_code}: {refresh_response.text}")
                return None

        except Exception as e:
            self._log(f"❌ Token refresh error: {e}")
            return None

    def login_with_refresh(self, refresh_token: str) -> Optional[OAuthTokens]:
        """Login using refresh token (convenience method)

        Args:
            refresh_token: The refresh token to use

        Returns:
            New OAuthTokens object or None if refresh failed
        """
        return self.refresh_tokens(refresh_token)

    def login_or_refresh(self, email: str, password: str, existing_tokens: Optional[OAuthTokens] = None) -> OAuthTokens:
        """Smart login that uses refresh token if available and valid, otherwise performs full login

        Args:
            email: User email
            password: User password
            existing_tokens: Existing tokens to check for refresh capability

        Returns:
            Valid OAuthTokens object
        """
        # Try refresh first if we have existing tokens
        if existing_tokens and existing_tokens.has_refresh_token():
            if existing_tokens.expires_soon():
                self._log("🔄 Token expires soon, attempting refresh...")
                refreshed_tokens = self.refresh_tokens(existing_tokens.refresh_token)
                if refreshed_tokens:
                    return refreshed_tokens
                else:
                    self._log("⚠️ Refresh failed, falling back to full login")
            elif not existing_tokens.is_expired():
                self._log("✅ Existing tokens are still valid")
                return existing_tokens

        # Fall back to full login
        self._log("🔐 Performing full login...")
        return self.login(email, password)
