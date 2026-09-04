import pytest

from src.services.hermes.client import validate_saas_url


def test_url_policy_development_loopback_ipv4_allowed():
    assert validate_saas_url("http://127.0.0.1:8000", environment="development") == "http://127.0.0.1:8000"


def test_url_policy_development_loopback_localhost_allowed():
    assert validate_saas_url("http://localhost:8000", environment="development") == "http://localhost:8000"


def test_url_policy_development_loopback_ipv6_allowed():
    assert validate_saas_url("http://[::1]:8000", environment="development") == "http://[::1]:8000"


def test_url_policy_test_environment_loopback_allowed():
    assert validate_saas_url("http://127.0.0.1:8000", environment="test") == "http://127.0.0.1:8000"


def test_url_policy_development_insecure_remote_http_rejected():
    with pytest.raises(ValueError, match="loopback"):
        validate_saas_url("http://192.168.1.50:8000", environment="development")
    with pytest.raises(ValueError, match="loopback"):
        validate_saas_url("http://api.kontraktor.com", environment="development")


def test_url_policy_staging_loopback_http_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_saas_url("http://127.0.0.1:8000", environment="staging")
    with pytest.raises(ValueError, match="HTTPS"):
        validate_saas_url("http://localhost:8000", environment="staging")


def test_url_policy_production_loopback_http_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_saas_url("http://127.0.0.1:8000", environment="production")
    with pytest.raises(ValueError, match="HTTPS"):
        validate_saas_url("http://localhost:8000", environment="production")


def test_url_policy_https_remains_allowed_everywhere():
    assert validate_saas_url("https://saas.test", environment="development") == "https://saas.test"
    assert validate_saas_url("https://saas.test", environment="staging") == "https://saas.test"
    assert validate_saas_url("https://saas.test", environment="production") == "https://saas.test"
    assert validate_saas_url("https://api.kontraktor.com:443", environment="production") == "https://api.kontraktor.com:443"
