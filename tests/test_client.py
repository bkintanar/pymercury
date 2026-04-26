"""Tests for MercuryClient and CompleteAccountData (pymercury/client.py).

Heavily uses unittest.mock to stub out MercuryOAuthClient.authenticate /
MercuryAPIClient methods so no real HTTP is performed.
"""

from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from pymercury import (
    Account,
    CompleteAccountData,
    CustomerInfo,
    MercuryClient,
    MercuryConfig,
    Service,
    ServiceIds,
    authenticate,
    get_complete_data,
)
from pymercury.exceptions import MercuryError, MercuryOAuthError
from pymercury.oauth import OAuthTokens


# ---- CompleteAccountData ---------------------------------------------------


class TestCompleteAccountData:
    def test_properties(self, fake_oauth_token_data):
        tokens = OAuthTokens(fake_oauth_token_data)
        accounts = [Account({"accountId": "a1"}), Account({"accountId": None})]
        services = [Service({"serviceId": "s1", "serviceGroup": "electricity"})]
        ids = ServiceIds(services)
        data = CompleteAccountData(
            tokens=tokens,
            customer_info=CustomerInfo({"customerId": "c1"}),
            accounts=accounts,
            services=services,
            service_ids=ids,
        )
        assert data.customer_id == "cust-test"
        assert data.account_ids == ["a1"]  # filters out None
        assert data.access_token == tokens.access_token
        assert data.email == "test@example.com"
        assert data.name == "Test User"


# ---- MercuryClient init / lifecycle ----------------------------------------


@pytest.fixture
def stub_client():
    """Build a MercuryClient with the OAuth client and any future API client mocked."""
    c = MercuryClient("e@x.com", "pw", verbose=True)
    c.oauth_client = MagicMock()
    return c


class TestInitAndLogging:
    def test_log_writes_when_verbose(self, capsys):
        c = MercuryClient("e", "p", verbose=True)
        c._log("hello")
        assert "hello" in capsys.readouterr().out

    def test_log_silent_when_not_verbose(self, capsys):
        c = MercuryClient("e", "p", verbose=False)
        c._log("hello")
        assert capsys.readouterr().out == ""


class TestLogin:
    def test_login_success(self, stub_client, fake_oauth_token_data):
        tokens = OAuthTokens(fake_oauth_token_data)
        stub_client.oauth_client.authenticate.return_value = tokens
        result = stub_client.login()
        assert result is tokens
        assert stub_client.is_logged_in
        assert stub_client._api_client is not None

    def test_login_raises_when_no_access_token(self, stub_client):
        empty = OAuthTokens({})  # access_token=None
        stub_client.oauth_client.authenticate.return_value = empty
        with pytest.raises(MercuryOAuthError):
            stub_client.login()


class TestSmartLogin:
    def test_delegates_to_login_or_refresh(self, stub_client, fake_oauth_token_data):
        tokens = OAuthTokens(fake_oauth_token_data)
        stub_client.oauth_client.login_or_refresh.return_value = tokens
        result = stub_client.smart_login(existing_tokens=tokens)
        assert result is tokens
        assert stub_client._api_client is not None
        stub_client.oauth_client.login_or_refresh.assert_called_once_with(tokens)


class TestRefreshIfNeeded:
    def test_returns_false_when_no_tokens(self, stub_client):
        assert stub_client.refresh_if_needed() is False

    def test_returns_false_when_not_expiring(self, stub_client, fake_oauth_token_data):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        with freeze_time("2026-01-01 12:30:00"):
            assert stub_client.refresh_if_needed() is False

    def test_refreshes_when_expiring_soon(self, stub_client, fake_oauth_token_data, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        new_tokens = OAuthTokens({"access_token": fake_jwt(), "expires_in": 3600})
        stub_client.oauth_client.refresh_tokens.return_value = new_tokens
        with freeze_time("2026-01-01 12:58:00"):
            assert stub_client.refresh_if_needed() is True
        assert stub_client._tokens is new_tokens
        assert stub_client._api_client is not None

    def test_returns_false_when_refresh_fails(self, stub_client, fake_oauth_token_data):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        stub_client.oauth_client.refresh_tokens.return_value = None
        with freeze_time("2026-01-01 12:58:00"):
            assert stub_client.refresh_if_needed() is False


class TestEnsureLoggedIn:
    def test_raises_when_not_logged_in(self, stub_client):
        with pytest.raises(MercuryError, match="Must call login"):
            stub_client._ensure_logged_in()

    def test_expired_with_refresh_succeeds(self, stub_client, fake_oauth_token_data, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        stub_client._api_client = MagicMock()
        new_tokens = OAuthTokens({"access_token": fake_jwt(), "expires_in": 3600})
        stub_client.oauth_client.refresh_tokens.return_value = new_tokens
        with freeze_time("2026-01-01 14:00:00"):  # token expired
            stub_client._ensure_logged_in()
        assert stub_client._tokens is new_tokens

    def test_expired_refresh_fails_raises(self, stub_client, fake_oauth_token_data):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        stub_client._api_client = MagicMock()
        stub_client.oauth_client.refresh_tokens.return_value = None
        with freeze_time("2026-01-01 14:00:00"):
            with pytest.raises(MercuryError, match="refresh failed"):
                stub_client._ensure_logged_in()

    def test_expired_no_refresh_token_raises(self, stub_client, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens({
                "access_token": fake_jwt(),
                "expires_in": 3600,
                # no refresh_token
            })
        stub_client._api_client = MagicMock()
        with freeze_time("2026-01-01 14:00:00"):
            with pytest.raises(MercuryError, match="no refresh token"):
                stub_client._ensure_logged_in()

    def test_expires_soon_proactively_refreshes(self, stub_client, fake_oauth_token_data, fake_jwt):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        stub_client._api_client = MagicMock()
        new_tokens = OAuthTokens({"access_token": fake_jwt(), "expires_in": 3600})
        stub_client.oauth_client.refresh_tokens.return_value = new_tokens
        with freeze_time("2026-01-01 12:58:00"):  # expires_soon but not expired
            stub_client._ensure_logged_in()
        assert stub_client._tokens is new_tokens


# ---- get_complete_account_data ---------------------------------------------


class TestGetCompleteAccountData:
    def test_happy_path(self, stub_client, fake_oauth_token_data):
        stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        api = MagicMock()
        api.get_customer_info.return_value = CustomerInfo({"customerId": "cust-test"})
        api.get_accounts.return_value = [Account({"accountId": "a1"})]
        api.get_all_services.return_value = [Service({"serviceId": "E1", "serviceGroup": "electricity"})]
        stub_client._api_client = api
        result = stub_client.get_complete_account_data()
        assert isinstance(result, CompleteAccountData)
        assert result.customer_id == "cust-test"
        assert result.account_ids == ["a1"]
        assert result.service_ids.electricity == ["E1"]

    def test_raises_when_no_customer_id_in_tokens(self, stub_client):
        # Tokens with no JWT => no customer_id
        stub_client._tokens = OAuthTokens({})
        stub_client._api_client = MagicMock()
        with pytest.raises(MercuryError, match="Customer ID"):
            stub_client.get_complete_account_data()

    def test_raises_when_no_accounts(self, stub_client, fake_oauth_token_data):
        stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        api = MagicMock()
        api.get_customer_info.return_value = CustomerInfo({})
        api.get_accounts.return_value = []
        stub_client._api_client = api
        with pytest.raises(MercuryError, match="No customer accounts"):
            stub_client.get_complete_account_data()


# ---- Properties ------------------------------------------------------------


class TestProperties:
    def test_when_not_logged_in(self):
        c = MercuryClient("e", "p")
        assert c.is_logged_in is False
        assert c.customer_id is None
        assert c.access_token is None
        assert c.email is None
        assert c.name is None
        assert c.account_ids == []
        assert c.service_ids is None
        assert c.api is None
        assert c.oauth is c.oauth_client

    def test_when_logged_in(self, stub_client, fake_oauth_token_data):
        stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        stub_client._api_client = MagicMock()
        stub_client._accounts = [Account({"accountId": "a1"})]
        stub_client._service_ids = ServiceIds([])
        assert stub_client.is_logged_in is True
        assert stub_client.customer_id == "cust-test"
        assert stub_client.account_ids == ["a1"]
        assert stub_client.service_ids is not None
        assert stub_client.access_token is not None
        assert stub_client.email == "test@example.com"
        assert stub_client.name == "Test User"
        assert stub_client.api is stub_client._api_client


# ---- save / load tokens ----------------------------------------------------


class TestSaveLoadTokens:
    def test_save_when_no_tokens_returns_empty_dict(self, stub_client):
        assert stub_client.save_tokens() == {}

    def test_save_with_expires_at(self, stub_client, fake_oauth_token_data):
        with freeze_time("2026-01-01 12:00:00"):
            stub_client._tokens = OAuthTokens(fake_oauth_token_data)
        saved = stub_client.save_tokens()
        assert saved["access_token"] == fake_oauth_token_data["access_token"]
        assert saved["refresh_token"] == "rt_test_123"
        assert saved["expires_at"] == "2026-01-01T13:00:00"

    def test_save_with_no_expires_at(self, stub_client):
        stub_client._tokens = OAuthTokens({})  # no expires_at
        saved = stub_client.save_tokens()
        assert saved["expires_at"] is None

    def test_load_valid_tokens(self, stub_client, fake_oauth_token_data, fake_jwt):
        # HIGH-4 fix: round-trip preserves expires_at and is_expired returns False.
        with freeze_time("2026-01-01 12:00:00"):
            saved = {
                "access_token": fake_jwt(),
                "refresh_token": "rt",
                "expires_in": 3600,
                "token_type": "Bearer",
                "expires_at": "2026-01-01T13:00:00",
            }
        with freeze_time("2026-01-01 12:30:00"):
            assert stub_client.load_tokens(saved) is True
        assert stub_client._tokens is not None
        assert stub_client._api_client is not None

    def test_load_expired_with_successful_refresh(self, stub_client, fake_jwt):
        saved = {
            "access_token": fake_jwt(),
            "refresh_token": "rt",
            "expires_at": "2026-01-01T00:00:00",
        }
        new = OAuthTokens({"access_token": fake_jwt(), "expires_in": 3600})
        stub_client.oauth_client.refresh_tokens.return_value = new
        with freeze_time("2026-04-01 00:00:00"):
            result = stub_client.load_tokens(saved)
        assert result is True
        assert stub_client._tokens is new

    def test_load_expired_refresh_fails(self, stub_client, fake_jwt):
        saved = {
            "access_token": fake_jwt(),
            "refresh_token": "rt",
            "expires_at": "2026-01-01T00:00:00",
        }
        stub_client.oauth_client.refresh_tokens.return_value = None
        with freeze_time("2026-04-01 00:00:00"):
            assert stub_client.load_tokens(saved) is False

    def test_load_expired_no_refresh_token(self, stub_client, fake_jwt):
        saved = {
            "access_token": fake_jwt(),
            "expires_at": "2026-01-01T00:00:00",
        }
        with freeze_time("2026-04-01 00:00:00"):
            assert stub_client.load_tokens(saved) is False

    def test_load_no_access_token_returns_false(self, stub_client):
        # No access_token => no _api_client created => fall through to return False
        saved = {"refresh_token": "rt"}
        assert stub_client.load_tokens(saved) is False

    def test_load_handles_unexpected_exception(self, stub_client):
        # OAuthTokens() on non-dict raises AttributeError; the broad except
        # branch logs and returns False.
        assert stub_client.load_tokens("not-a-dict") is False  # type: ignore[arg-type]


class TestLoginWithSavedTokens:
    def test_uses_saved_tokens_when_valid(self, stub_client, fake_jwt):
        saved = {
            "access_token": fake_jwt(),
            "refresh_token": "rt",
            "expires_at": "2026-12-31T23:59:59",
        }
        with freeze_time("2026-01-01 12:00:00"):
            result = stub_client.login_with_saved_tokens(saved)
        assert result is stub_client._tokens

    def test_falls_back_to_smart_login_when_saved_tokens_invalid(
        self, stub_client, fake_oauth_token_data
    ):
        new = OAuthTokens(fake_oauth_token_data)
        stub_client.oauth_client.login_or_refresh.return_value = new
        # token_data with no access_token won't load_tokens successfully.
        result = stub_client.login_with_saved_tokens({"refresh_token": "rt"})
        assert result is new

    def test_no_saved_tokens_uses_smart_login(self, stub_client, fake_oauth_token_data):
        new = OAuthTokens(fake_oauth_token_data)
        stub_client.oauth_client.login_or_refresh.return_value = new
        result = stub_client.login_with_saved_tokens(None)
        assert result is new


# ---- Context manager / close ------------------------------------------------


class TestContextManager:
    def test_close_with_no_api_client(self):
        c = MercuryClient("e", "p")
        c.oauth_client = MagicMock()
        c.close()
        c.oauth_client.close.assert_called_once()

    def test_close_with_api_client(self):
        c = MercuryClient("e", "p")
        c.oauth_client = MagicMock()
        c._api_client = MagicMock()
        c.close()
        c.oauth_client.close.assert_called_once()
        c._api_client.close.assert_called_once()

    def test_with_block(self):
        c = MercuryClient("e", "p")
        c.oauth_client = MagicMock()
        with c as inner:
            assert inner is c
        c.oauth_client.close.assert_called_once()


# ---- Convenience module-level functions -------------------------------------


class TestConvenienceFunctions:
    def test_authenticate_returns_tokens(self, fake_oauth_token_data):
        tokens = OAuthTokens(fake_oauth_token_data)
        with patch("pymercury.client.MercuryClient") as MC:
            instance = MC.return_value
            instance.login.return_value = tokens
            result = authenticate("e", "p")
        assert result is tokens
        MC.assert_called_once_with("e", "p", None, False)

    def test_get_complete_data_returns_complete_data(self):
        with patch("pymercury.client.MercuryClient") as MC:
            instance = MC.return_value
            sentinel = object()
            instance.get_complete_account_data.return_value = sentinel
            result = get_complete_data("e", "p", config=MercuryConfig(timeout=30), verbose=True)
        assert result is sentinel
        instance.login.assert_called_once()
        instance.get_complete_account_data.assert_called_once()
