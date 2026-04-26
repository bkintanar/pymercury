"""Comprehensive tests for OAuthTokens and MercuryOAuthClient.

Covers the full OAuth 2.0 PKCE + Azure B2C flow using requests-mock to
intercept HTTP calls, and freezegun to make expiry math deterministic.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import quote

import pytest
import requests
from freezegun import freeze_time

from pymercury.config import MercuryConfig
from pymercury.exceptions import (
    MercuryAuthenticationError,
    MercuryOAuthError,
)
from pymercury.oauth.client import MercuryOAuthClient, OAuthTokens


# ---- Helpers ----------------------------------------------------------------


def _b2c_html_with_settings(csrf="csrf-token", trans_id="tx-1"):
    """HTML response that contains both the inline `"csrf"`/`"transId"` JSON
    blob AND a `var SETTINGS = {...};` block — covers both Step 1 and Step 3a
    extractions."""
    return (
        '<html><body><script>'
        f'var data = {{"csrf":"{csrf}","transId":"{trans_id}"}};'
        f'var SETTINGS = {{"csrf":"{csrf}","transId":"{trans_id}"}};'
        '</script></body></html>'
    )


# ---- OAuthTokens ------------------------------------------------------------


class TestOAuthTokens:
    def test_full_token_data_extracts_all_fields(self, fake_oauth_token_data):
        tokens = OAuthTokens(fake_oauth_token_data)
        assert tokens.access_token == fake_oauth_token_data["access_token"]
        assert tokens.refresh_token == "rt_test_123"
        assert tokens.expires_in == 3600
        assert tokens.token_type == "Bearer"
        # Extracted from JWT claims (see conftest.make_fake_jwt defaults)
        assert tokens.customer_id == "cust-test"
        assert tokens.account_id == "acc-test"
        assert tokens.service_id == "svc-test"
        assert tokens.email == "test@example.com"
        assert tokens.name == "Test User"

    def test_minimal_token_data_has_no_user_info(self):
        # No access_token => no JWT decoding => no user info attributes.
        tokens = OAuthTokens({})
        assert tokens.access_token is None
        assert tokens.refresh_token is None
        assert tokens.token_type == "Bearer"  # default
        assert tokens.expires_at is None
        assert tokens.customer_id is None
        assert tokens.email is None
        assert tokens.name is None  # given+family empty => None

    def test_name_is_only_given_or_family_when_one_missing(self, fake_jwt):
        tokens = OAuthTokens({
            "access_token": fake_jwt({"given_name": "Solo"}),
        })
        assert tokens.name == "Solo"

    def test_invalid_jwt_does_not_set_user_info(self):
        # decode_jwt_payload returns None; for-loop never enters.
        tokens = OAuthTokens({"access_token": "not.a.valid_jwt_payload"})
        assert tokens.customer_id is None

    def test_saved_expires_at_is_honored(self, fake_jwt):
        # HIGH-4 fix: when expires_at ISO string is in token_data,
        # use it directly instead of recomputing now + expires_in.
        saved = "2026-01-01T13:00:00"
        tokens = OAuthTokens({
            "access_token": fake_jwt(),
            "expires_in": 3600,
            "expires_at": saved,
        })
        assert tokens.expires_at == datetime(2026, 1, 1, 13, 0, 0)

    def test_saved_expires_at_invalid_falls_to_none(self):
        tokens = OAuthTokens({
            "access_token": None,
            "expires_in": None,
            "expires_at": "not-an-iso-date",
        })
        assert tokens.expires_at is None

    @freeze_time("2026-01-01 12:00:00")
    def test_expires_at_computed_from_expires_in(self, fake_jwt):
        tokens = OAuthTokens({
            "access_token": fake_jwt(),
            "expires_in": 3600,
        })
        assert tokens.expires_at == datetime(2026, 1, 1, 13, 0, 0)

    @freeze_time("2026-01-01 12:00:00")
    def test_is_expired_when_no_expires_at(self):
        tokens = OAuthTokens({"access_token": None})
        assert tokens.is_expired() is False
        assert tokens.expires_soon() is False
        assert tokens.time_until_expiry() is None

    def test_is_expired_round_trip(self, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            tokens = OAuthTokens({
                "access_token": fake_jwt(),
                "expires_in": 3600,
            })
        with freeze_time("2026-01-01 13:00:01"):
            assert tokens.is_expired() is True
        with freeze_time("2026-01-01 12:30:00"):
            assert tokens.is_expired() is False

    def test_expires_soon_within_buffer(self, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            tokens = OAuthTokens({
                "access_token": fake_jwt(),
                "expires_in": 3600,
            })
        # 56 minutes in = 4 minutes from expiry, default buffer 5 minutes.
        with freeze_time("2026-01-01 12:56:00"):
            assert tokens.expires_soon() is True
        with freeze_time("2026-01-01 12:30:00"):
            assert tokens.expires_soon(buffer_minutes=5) is False

    def test_has_refresh_token(self, fake_jwt):
        with_rt = OAuthTokens({"refresh_token": "rt"})
        without_rt = OAuthTokens({})
        assert with_rt.has_refresh_token() is True
        assert without_rt.has_refresh_token() is False

    def test_time_until_expiry(self, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            tokens = OAuthTokens({
                "access_token": fake_jwt(),
                "expires_in": 3600,
            })
        with freeze_time("2026-01-01 12:00:00"):
            assert tokens.time_until_expiry() == timedelta(hours=1)


# ---- MercuryOAuthClient -----------------------------------------------------


class TestOAuthClientInit:
    def test_initialization_sets_pkce_and_state(self):
        client = MercuryOAuthClient("e@x.com", "pw")
        assert client.email == "e@x.com"
        assert client.password == "pw"
        assert client.code_verifier
        assert client.code_challenge
        assert client.state.startswith("state_")
        assert client.nonce.startswith("nonce_")

    def test_log_writes_when_verbose(self, capsys):
        client = MercuryOAuthClient("e", "p", verbose=True)
        client._log("hello")
        out = capsys.readouterr().out
        assert "hello" in out

    def test_log_silent_when_not_verbose(self, capsys):
        client = MercuryOAuthClient("e", "p", verbose=False)
        client._log("hello")
        assert capsys.readouterr().out == ""

    def test_close_and_context_manager(self):
        client = MercuryOAuthClient("e", "p")
        with client as c:
            assert c is client
        # Calling close again is safe.
        client.close()


class TestRefreshTokens:
    def test_refresh_success(self, requests_mock, fake_jwt):
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, json={
            "access_token": fake_jwt(),
            "refresh_token": "new_rt",
            "expires_in": 3600,
            "token_type": "Bearer",
        })
        result = client.refresh_tokens("old_rt")
        assert isinstance(result, OAuthTokens)
        assert result.refresh_token == "new_rt"

    def test_refresh_non_200_returns_none(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, status_code=400, text="bad")
        assert client.refresh_tokens("old_rt") is None

    def test_refresh_request_exception_returns_none(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, exc=requests.exceptions.ConnectionError("dns"))
        assert client.refresh_tokens("old_rt") is None

    def test_login_with_refresh_delegates_to_refresh_tokens(self, requests_mock, fake_jwt):
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, json={
            "access_token": fake_jwt(),
            "expires_in": 3600,
        })
        result = client.login_with_refresh("rt")
        assert isinstance(result, OAuthTokens)


class TestLoginOrRefresh:
    def test_returns_existing_tokens_when_valid(self, fake_oauth_token_data):
        client = MercuryOAuthClient("e", "p")
        with freeze_time("2026-01-01 12:00:00"):
            existing = OAuthTokens(fake_oauth_token_data)
        with freeze_time("2026-01-01 12:30:00"):  # not expiring soon
            result = client.login_or_refresh(existing_tokens=existing)
        assert result is existing

    def test_refreshes_when_expiring_soon(self, fake_oauth_token_data, fake_jwt, requests_mock):
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, json={
            "access_token": fake_jwt(),
            "refresh_token": "fresh_rt",
            "expires_in": 3600,
        })
        with freeze_time("2026-01-01 12:00:00"):
            existing = OAuthTokens(fake_oauth_token_data)
        with freeze_time("2026-01-01 12:58:00"):  # 2 min until expiry
            result = client.login_or_refresh(existing_tokens=existing)
        assert result.refresh_token == "fresh_rt"

    def test_falls_back_to_authenticate_when_refresh_fails(self, fake_oauth_token_data, requests_mock):
        # CRITICAL-1 reproducer: the previous code called self.login() which
        # didn't exist. After fix, falls back to self.authenticate().
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, status_code=400)  # refresh fails
        with freeze_time("2026-01-01 12:00:00"):
            existing = OAuthTokens(fake_oauth_token_data)
        sentinel = object()
        with patch.object(client, "authenticate", return_value=sentinel) as auth:
            with freeze_time("2026-01-01 12:58:00"):
                result = client.login_or_refresh(existing_tokens=existing)
            auth.assert_called_once_with()
        assert result is sentinel

    def test_falls_back_to_authenticate_when_no_existing_tokens(self):
        client = MercuryOAuthClient("e", "p")
        sentinel = object()
        with patch.object(client, "authenticate", return_value=sentinel) as auth:
            result = client.login_or_refresh(existing_tokens=None)
            auth.assert_called_once_with()
        assert result is sentinel


# ---- Full authenticate() flow ----------------------------------------------


def _register_full_oauth_flow(requests_mock, config, fake_jwt, code="auth_code_xyz"):
    """Wire up all 6 HTTP endpoints required by authenticate()."""
    base = config.base_url
    pol = config.policy
    auth_url = f"{base}/{pol}/oauth2/v2.0/authorize"
    selfasserted = f"{base}/{pol}/SelfAsserted"
    combined = f"{base}/{pol}/api/CombinedSigninAndSignup/confirmed"
    token_url = f"{base}/{pol}/oauth2/v2.0/token"

    # Step 1 + Step 3a — both GETs to the authorize page return HTML
    # containing csrf/transId AND a SETTINGS object.
    requests_mock.get(auth_url, text=_b2c_html_with_settings())
    # Step 2 + Step 3b — credential POSTs return {"status":"200"}
    requests_mock.post(selfasserted, text='{"status":"200"}')
    # Step 3c — combined POST returns a 302 redirect with the auth code
    requests_mock.post(
        combined,
        status_code=302,
        headers={"Location": f"{config.redirect_uri}/?code={code}&state=s"},
    )
    # Step 4 — token exchange returns JWT-bearing token data.
    requests_mock.post(token_url, json={
        "access_token": fake_jwt(),
        "refresh_token": "rt_done",
        "expires_in": 3600,
        "token_type": "Bearer",
    })


class TestAuthenticateHappyPath:
    def test_full_flow_returns_tokens(self, requests_mock, fake_jwt):
        client = MercuryOAuthClient("e@x.com", "pw")
        _register_full_oauth_flow(requests_mock, client.config, fake_jwt)
        tokens = client.authenticate()
        assert isinstance(tokens, OAuthTokens)
        assert tokens.refresh_token == "rt_done"


class TestAuthenticateFailures:
    def test_missing_csrf_in_html_raises_value_error(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        auth_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/authorize"
        requests_mock.get(auth_url, text="<html>no fields</html>")
        with pytest.raises(ValueError):
            client.authenticate()

    def test_credential_rejection_raises_authentication_error(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        auth_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/authorize"
        selfasserted = f"{client.config.base_url}/{client.config.policy}/SelfAsserted"
        requests_mock.get(auth_url, text=_b2c_html_with_settings())
        requests_mock.post(selfasserted, text='{"status":"401"}')
        with pytest.raises(MercuryAuthenticationError):
            client.authenticate()

    def test_when_settings_block_missing_raises_oauth_error(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        auth_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/authorize"
        selfasserted = f"{client.config.base_url}/{client.config.policy}/SelfAsserted"
        # Step 1 succeeds, Step 2 succeeds, Step 3a HTML lacks SETTINGS.
        # We need 2 different responses for the same URL — sequential mocks.
        requests_mock.get(
            auth_url,
            [
                {"text": _b2c_html_with_settings()},
                {"text": '<html>{"csrf":"c","transId":"t"} no settings here</html>'},
            ],
        )
        requests_mock.post(selfasserted, text='{"status":"200"}')
        with pytest.raises(MercuryOAuthError):
            client.authenticate()

    def test_when_settings_missing_csrf_returns_none_and_raises(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        auth_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/authorize"
        selfasserted = f"{client.config.base_url}/{client.config.policy}/SelfAsserted"
        requests_mock.get(
            auth_url,
            [
                {"text": _b2c_html_with_settings()},
                # SETTINGS regex matches but lacks csrf/transId
                {"text": '<html><script>var SETTINGS = {"foo":"bar"};</script></html>'},
            ],
        )
        requests_mock.post(selfasserted, text='{"status":"200"}')
        with pytest.raises(MercuryOAuthError):
            client.authenticate()

    def test_when_settings_json_invalid_returns_none_and_raises(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        auth_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/authorize"
        selfasserted = f"{client.config.base_url}/{client.config.policy}/SelfAsserted"
        requests_mock.get(
            auth_url,
            [
                {"text": _b2c_html_with_settings()},
                # SETTINGS regex matches but content is not JSON.
                {"text": '<html><script>var SETTINGS = {invalid json};</script></html>'},
            ],
        )
        requests_mock.post(selfasserted, text='{"status":"200"}')
        with pytest.raises(MercuryOAuthError):
            client.authenticate()

    def test_b2c_get_non_200_returns_none_and_raises(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        auth_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/authorize"
        selfasserted = f"{client.config.base_url}/{client.config.policy}/SelfAsserted"
        # Fresh-session GET (Step 3a) returns 500 — _mercury_b2c_fresh_flow
        # falls through with `return None`, authenticate() raises.
        requests_mock.get(
            auth_url,
            [
                {"text": _b2c_html_with_settings()},  # Step 1
                {"status_code": 500, "text": "fail"},  # Step 3a
            ],
        )
        requests_mock.post(selfasserted, text='{"status":"200"}')
        with pytest.raises(MercuryOAuthError):
            client.authenticate()

    def test_combined_signin_non_redirect_returns_none(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        base = client.config.base_url
        pol = client.config.policy
        requests_mock.get(f"{base}/{pol}/oauth2/v2.0/authorize", text=_b2c_html_with_settings())
        requests_mock.post(f"{base}/{pol}/SelfAsserted", text='{"status":"200"}')
        # Combined POST returns 200 (not a redirect) -> path falls through,
        # _mercury_combined_signin_post returns None, authenticate raises.
        requests_mock.post(
            f"{base}/{pol}/api/CombinedSigninAndSignup/confirmed",
            status_code=200,
            text="ok",
        )
        with pytest.raises(MercuryOAuthError):
            client.authenticate()

    def test_fresh_session_auth_non_200_returns_none(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        base = client.config.base_url
        pol = client.config.policy
        requests_mock.get(f"{base}/{pol}/oauth2/v2.0/authorize", text=_b2c_html_with_settings())
        # First SelfAsserted (Step 2) succeeds, second (Step 3b on fresh
        # session) fails with 401.
        requests_mock.post(
            f"{base}/{pol}/SelfAsserted",
            [
                {"text": '{"status":"200"}'},
                {"status_code": 401, "text": "denied"},
            ],
        )
        with pytest.raises(MercuryOAuthError):
            client.authenticate()

    def test_fresh_session_auth_status_not_200_returns_none(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        base = client.config.base_url
        pol = client.config.policy
        requests_mock.get(f"{base}/{pol}/oauth2/v2.0/authorize", text=_b2c_html_with_settings())
        requests_mock.post(
            f"{base}/{pol}/SelfAsserted",
            [
                {"text": '{"status":"200"}'},
                {"text": '{"status":"401"}'},  # auth result has wrong status
            ],
        )
        with pytest.raises(MercuryOAuthError):
            client.authenticate()


class TestRedirectFollowing:
    def test_auth_code_in_response_url(self, requests_mock):
        """When the combined response URL itself contains ?code=, no follow needed."""
        client = MercuryOAuthClient("e", "p")
        # Build a fake response object with .url containing the code.
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.url = "https://callback.example/?code=direct_code"
        fake_response.headers = {}
        result = client._follow_redirects_for_code(fake_response)
        assert result == "direct_code"

    def test_auth_code_in_location_header(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.url = "https://no-code.example/"
        fake_response.headers = {"Location": "https://callback.example/?code=loc_code"}
        result = client._follow_redirects_for_code(fake_response)
        assert result == "loc_code"

    def test_no_location_breaks_loop_then_raises(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.url = "https://no-code.example/"
        fake_response.headers = {}  # no Location, exits loop
        with pytest.raises(MercuryOAuthError, match="Could not find authorization code"):
            client._follow_redirects_for_code(fake_response)

    def test_request_exception_during_follow_breaks_loop(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        # Mock a redirect chain: first response has Location to a URL that
        # raises ConnectionError on GET. The except branch breaks the loop.
        from unittest.mock import MagicMock

        next_url = "https://will-fail.example/next"
        fake_response = MagicMock()
        fake_response.url = "https://no-code.example/"
        fake_response.headers = {"Location": next_url}
        requests_mock.get(next_url, exc=requests.exceptions.ConnectionError("boom"))
        with pytest.raises(MercuryOAuthError):
            client._follow_redirects_for_code(fake_response)

    def test_relative_location_is_resolved(self, requests_mock, fake_jwt):
        client = MercuryOAuthClient("e", "p")
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.url = "https://example.com/page"
        fake_response.headers = {"Location": "/callback?code=relative_code"}
        # Code is found in the Location header before any GET happens.
        result = client._follow_redirects_for_code(fake_response)
        assert result == "relative_code"

    def test_max_redirects_exhausted_raises(self):
        client = MercuryOAuthClient("e", "p", config=MercuryConfig(max_redirects=0))
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.url = "https://no-code.example/"
        fake_response.headers = {"Location": "https://still-no-code.example/"}
        with pytest.raises(MercuryOAuthError):
            client._follow_redirects_for_code(fake_response)


class TestExchangeCodeForToken:
    def test_non_200_raises_for_status(self, requests_mock):
        client = MercuryOAuthClient("e", "p")
        token_url = f"{client.config.base_url}/{client.config.policy}/oauth2/v2.0/token"
        requests_mock.post(token_url, status_code=400)
        with pytest.raises(requests.HTTPError):
            client._exchange_code_for_token("code", "verifier")


class TestCombinedSigninExceptions:
    def test_request_exception_in_combined_post_returns_none(self, requests_mock):
        """Trigger the except branch in _mercury_combined_signin_post via a
        RequestException on the token exchange step."""
        client = MercuryOAuthClient("e", "p")
        base = client.config.base_url
        pol = client.config.policy
        requests_mock.get(f"{base}/{pol}/oauth2/v2.0/authorize", text=_b2c_html_with_settings())
        requests_mock.post(f"{base}/{pol}/SelfAsserted", text='{"status":"200"}')
        requests_mock.post(
            f"{base}/{pol}/api/CombinedSigninAndSignup/confirmed",
            status_code=302,
            headers={"Location": f"{client.config.redirect_uri}/?code=abc"},
        )
        # Token exchange raises ConnectionError -> caught by except in
        # _mercury_combined_signin_post.
        requests_mock.post(
            f"{base}/{pol}/oauth2/v2.0/token",
            exc=requests.exceptions.ConnectionError("boom"),
        )
        with pytest.raises(MercuryOAuthError):
            client.authenticate()


class TestCookieCopying:
    def test_authenticate_copies_session_cookies_to_fresh_session(
        self, requests_mock, fake_jwt
    ):
        """The for-cookie loop in _mercury_b2c_fresh_flow needs at least
        one cookie on the original session to exercise."""
        client = MercuryOAuthClient("e@x.com", "pw")
        client.session.cookies.set("preset", "value", domain="login.mercury.co.nz", path="/")
        _register_full_oauth_flow(requests_mock, client.config, fake_jwt)
        tokens = client.authenticate()
        assert isinstance(tokens, OAuthTokens)


class TestMultiHopRedirectChain:
    def test_two_hop_redirect_uses_fresh_session_and_finds_code(
        self, requests_mock, fake_jwt
    ):
        """CRITICAL-3 reproducer: redirects must be followed using the fresh
        session that holds B2C cookies. With a 2-hop chain the second hop
        should land on the URL containing ?code=."""
        client = MercuryOAuthClient("e@x.com", "pw")
        config = client.config
        base = config.base_url
        pol = config.policy
        auth_url = f"{base}/{pol}/oauth2/v2.0/authorize"
        selfasserted = f"{base}/{pol}/SelfAsserted"
        combined = f"{base}/{pol}/api/CombinedSigninAndSignup/confirmed"
        token_url = f"{base}/{pol}/oauth2/v2.0/token"
        hop1 = "https://hop1.example.com/middle"
        callback = f"{config.redirect_uri}/?code=multi_hop_code"

        requests_mock.get(auth_url, text=_b2c_html_with_settings())
        requests_mock.post(selfasserted, text='{"status":"200"}')
        requests_mock.post(combined, status_code=302, headers={"Location": hop1})
        # First hop returns another 302 with the auth code in Location.
        requests_mock.get(hop1, status_code=302, headers={"Location": callback})
        requests_mock.post(token_url, json={
            "access_token": fake_jwt(),
            "expires_in": 3600,
        })

        tokens = client.authenticate()
        assert isinstance(tokens, OAuthTokens)


class TestLoginOrRefreshExpiredFresh:
    def test_expired_with_refresh_token_falls_through_to_authenticate(
        self, fake_oauth_token_data
    ):
        """Branch 503->508: existing_tokens has refresh_token AND expires_soon
        is False AND is_expired is True — currently impossible (expires_soon
        returns True whenever expires_at <= now+buffer). To exercise the
        fall-through, use tokens with expires_at=None plus has_refresh_token."""
        client = MercuryOAuthClient("e", "p")
        # Token with refresh_token but no expires_at -> not expiring_soon,
        # not expired (both return False) -> elif not is_expired -> True ->
        # return existing_tokens. Already covered by test_returns_existing_tokens_when_valid.
        # The remaining unreachable branch is when has_refresh_token() True,
        # expires_soon() False, is_expired() True - inconsistent state.
        # Force it: monkey-patch is_expired to return True while keeping
        # expires_soon False.
        existing = OAuthTokens(fake_oauth_token_data)
        with patch.object(existing, "expires_soon", return_value=False), \
             patch.object(existing, "is_expired", return_value=True), \
             patch.object(client, "authenticate", return_value="auth-result") as auth:
            result = client.login_or_refresh(existing_tokens=existing)
            auth.assert_called_once_with()
        assert result == "auth-result"
