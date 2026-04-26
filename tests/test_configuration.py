#!/usr/bin/env python3
"""
Configuration system tests - converted from legacy test_mercury_library.py
"""

import pytest
from pymercury.config import MercuryConfig, default_config
from pymercury import MercuryAPIClient
from pymercury.exceptions import MercuryConfigError


# Every config-required field, with the env var name and the kwarg name.
# Used for parametrized validation-branch tests.
REQUIRED_FIELDS = [
    ("client_id", "MERCURY_CLIENT_ID"),
    ("redirect_uri", "MERCURY_REDIRECT_URI"),
    ("base_url", "MERCURY_BASE_URL"),
    ("policy", "MERCURY_POLICY"),
    ("scope", "MERCURY_SCOPE"),
    ("api_base_url", "MERCURY_API_BASE_URL"),
    ("api_subscription_key", "MERCURY_API_SUBSCRIPTION_KEY"),
]


@pytest.mark.parametrize("field,env_var", REQUIRED_FIELDS)
def test_validate_raises_when_required_field_empty(monkeypatch, field, env_var):
    """Each required field has a dedicated _validate branch that raises
    MercuryConfigError when the value is empty."""
    # Setting the env var to "" forces os.getenv to return "" (not the
    # hardcoded fallback default), so `client_id or os.getenv(...)` evaluates
    # to "" and the _validate branch fires.
    monkeypatch.setenv(env_var, "")
    kwargs = {field: ""}
    with pytest.raises(MercuryConfigError, match=field):
        MercuryConfig(**kwargs)


def test_validate_raises_when_timeout_is_zero():
    with pytest.raises(MercuryConfigError, match="timeout must be positive"):
        MercuryConfig(timeout=0)


def test_validate_raises_when_timeout_is_negative():
    with pytest.raises(MercuryConfigError, match="timeout must be positive"):
        MercuryConfig(timeout=-5)


def test_validate_raises_when_max_redirects_negative():
    with pytest.raises(MercuryConfigError, match="max_redirects"):
        MercuryConfig(max_redirects=-1)


def test_invalid_timeout_env_var_raises_config_error(monkeypatch):
    monkeypatch.setenv("MERCURY_TIMEOUT", "not-an-integer")
    with pytest.raises(MercuryConfigError, match="MERCURY_TIMEOUT"):
        MercuryConfig()


def test_invalid_max_redirects_env_var_raises_config_error(monkeypatch):
    monkeypatch.setenv("MERCURY_MAX_REDIRECTS", "abc")
    with pytest.raises(MercuryConfigError, match="MERCURY_MAX_REDIRECTS"):
        MercuryConfig()


def test_dotenv_import_success_path():
    """Reloading config with dotenv installed exercises the load_dotenv() success branch."""
    import importlib
    import sys

    sys.modules.pop("pymercury.config", None)
    cfg_mod = importlib.import_module("pymercury.config")
    assert cfg_mod.default_config is not None


def test_dotenv_import_failure_does_not_break_module(monkeypatch):
    """If python-dotenv is not installed, config import must still work."""
    import builtins
    import importlib
    import sys

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "dotenv":
            raise ImportError("simulated missing python-dotenv")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("pymercury.config", None)
    sys.modules.pop("dotenv", None)
    cfg_mod = importlib.import_module("pymercury.config")
    assert cfg_mod.default_config is not None
    # Restore module for downstream tests.
    monkeypatch.undo()
    sys.modules.pop("pymercury.config", None)
    importlib.import_module("pymercury.config")


class TestConfiguration:
    """Test configuration system functionality"""

    def test_default_config_loading(self):
        """Test that default configuration loads correctly"""
        assert default_config is not None
        assert hasattr(default_config, 'api_base_url')
        assert hasattr(default_config, 'timeout')
        assert hasattr(default_config, 'max_redirects')
        assert hasattr(default_config, 'user_agent')

        # Check default values are reasonable
        assert default_config.timeout > 0
        assert default_config.max_redirects > 0
        assert len(default_config.user_agent) > 0
        assert 'http' in default_config.api_base_url

    def test_custom_config_creation(self):
        """Test custom configuration creation"""
        custom_config = MercuryConfig(
            timeout=120,
            max_redirects=30,
            user_agent="TestApp/2.0",
            api_base_url="https://custom.api.url/v1"
        )

        assert custom_config.timeout == 120
        assert custom_config.max_redirects == 30
        assert custom_config.user_agent == "TestApp/2.0"
        assert custom_config.api_base_url == "https://custom.api.url/v1"

    def test_config_with_api_client(self):
        """Test that custom config works with API client"""
        custom_config = MercuryConfig(
            timeout=60,
            user_agent="CustomAgent/1.0"
        )

        client = MercuryAPIClient("dummy_token", config=custom_config)

        assert client.config.timeout == 60
        assert client.config.user_agent == "CustomAgent/1.0"

        # Headers should reflect custom user agent
        headers = client._build_headers()
        assert headers['User-Agent'] == "CustomAgent/1.0"

    def test_config_parameters(self):
        """Test all configuration parameters"""
        config = MercuryConfig(
            base_url="https://custom.oauth.url",
            api_base_url="https://custom.api.url",
            api_subscription_key="custom_key",
            timeout=90,
            max_redirects=20,
            user_agent="TestSuite/3.0"
        )

        assert config.base_url == "https://custom.oauth.url"
        assert config.api_base_url == "https://custom.api.url"
        assert config.api_subscription_key == "custom_key"
        assert config.timeout == 90
        assert config.max_redirects == 20
        assert config.user_agent == "TestSuite/3.0"

    def test_config_defaults(self):
        """Test that configuration uses appropriate defaults"""
        config = MercuryConfig()

        # Should have reasonable defaults for all required fields
        assert config.timeout >= 10  # At least 10 seconds
        assert config.max_redirects >= 5  # At least 5 redirects
        assert len(config.user_agent) > 0  # Should have user agent
        assert 'mercury' in config.api_base_url.lower()  # Should be Mercury API
        assert 'login.mercury' in config.base_url.lower()  # Should be Mercury OAuth

    def test_config_immutability(self):
        """Test that config objects can be modified after creation"""
        config = MercuryConfig(timeout=30)

        # Should be able to access attributes
        assert config.timeout == 30

        # Should be able to modify if needed (for testing)
        config.timeout = 60
        assert config.timeout == 60

    def test_config_with_different_clients(self):
        """Test that same config can be used with different clients"""
        config = MercuryConfig(
            timeout=45,
            user_agent="SharedConfig/1.0"
        )

        # Use with API client
        api_client = MercuryAPIClient("token1", config=config)
        assert api_client.config.timeout == 45
        assert api_client.config.user_agent == "SharedConfig/1.0"

        # Use with another API client
        api_client2 = MercuryAPIClient("token2", config=config)
        assert api_client2.config.timeout == 45
        assert api_client2.config.user_agent == "SharedConfig/1.0"

    def test_config_inheritance(self):
        """Test that unspecified config values use defaults"""
        # Create config with only some values
        partial_config = MercuryConfig(timeout=99)

        # Should have custom timeout
        assert partial_config.timeout == 99

        # Should inherit other values from defaults
        assert partial_config.max_redirects == default_config.max_redirects
        assert partial_config.api_base_url == default_config.api_base_url

    def test_config_url_validation(self):
        """Test that configuration accepts valid URLs"""
        config = MercuryConfig(
            base_url="https://test.mercury.co.nz/oauth",
            api_base_url="https://apis.test.mercury.co.nz/v1"
        )

        assert config.base_url.startswith('https://')
        assert config.api_base_url.startswith('https://')

    def test_config_environment_awareness(self):
        """Test that config can be used for different environments"""
        # Production config
        prod_config = MercuryConfig(
            api_base_url="https://apis.mercury.co.nz/selfservice/v1",
            timeout=20
        )

        # Development config
        dev_config = MercuryConfig(
            api_base_url="https://apis.test.mercury.co.nz/selfservice/v1",
            timeout=60,
            user_agent="Development/1.0"
        )

        assert prod_config.api_base_url != dev_config.api_base_url
        assert prod_config.timeout != dev_config.timeout

    def test_config_api_key_handling(self):
        """Test that API subscription key is handled correctly"""
        config = MercuryConfig(api_subscription_key="test_key_123")

        client = MercuryAPIClient("dummy_token", config=config)
        headers = client._build_headers()

        assert 'Ocp-Apim-Subscription-Key' in headers
        assert headers['Ocp-Apim-Subscription-Key'] == "test_key_123"
