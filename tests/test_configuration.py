import json

import pytest
from pydantic import ValidationError
from service_kit import ServiceKitBaseModel

from competitor_pulse.configuration import load_configuration
from tests.conftest import DATABASE_URL


def test_database_settings_load_from_environment():
    config = load_configuration()

    assert config.database.url.get_secret_value() == DATABASE_URL
    assert config.database.pool_min_size == 0
    assert config.database.pool_max_size == 10


def test_missing_database_url_names_the_field(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CP_DATABASE_URL")

    with pytest.raises(ValidationError, match="url"):
        load_configuration()


def test_empty_database_url_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CP_DATABASE_URL", "")

    with pytest.raises(ValidationError, match="url"):
        load_configuration()


def test_pool_max_size_below_min_size_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CP_DATABASE_POOL_MIN_SIZE", "5")
    monkeypatch.setenv("CP_DATABASE_POOL_MAX_SIZE", "2")

    with pytest.raises(ValidationError, match="pool_max_size"):
        load_configuration()


def test_logged_configuration_hides_secrets():
    # service-kit logs the configuration through ServiceKitBaseModel.to_json_dict().
    config = load_configuration()
    assert isinstance(config, ServiceKitBaseModel)

    logged = json.dumps(config.to_json_dict())

    assert DATABASE_URL not in logged
    assert "postgres:postgres" not in logged


def test_database_timeouts_have_defaults():
    config = load_configuration()

    assert config.database.connect_timeout_seconds == 5
    assert config.database.pool_timeout_seconds == 10
    assert config.database.ping_timeout_seconds == 5
    assert config.database.reconnect_timeout_seconds == 300


def test_database_timeouts_load_from_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CP_DATABASE_CONNECT_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("CP_DATABASE_POOL_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("CP_DATABASE_PING_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("CP_DATABASE_RECONNECT_TIMEOUT_SECONDS", "60")

    config = load_configuration()

    assert config.database.connect_timeout_seconds == 2
    assert config.database.pool_timeout_seconds == 1.5
    assert config.database.ping_timeout_seconds == 0.5
    assert config.database.reconnect_timeout_seconds == 60


@pytest.mark.parametrize(
    "field",
    [
        "connect_timeout_seconds",
        "pool_timeout_seconds",
        "ping_timeout_seconds",
        "reconnect_timeout_seconds",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1"])
def test_database_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch, field: str, value: str):
    monkeypatch.setenv(f"CP_DATABASE_{field.upper()}", value)

    with pytest.raises(ValidationError, match=field):
        load_configuration()


def test_page_size_above_max_page_size_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CP_API_SNAPSHOTS_PAGE_SIZE", "300")

    with pytest.raises(ValidationError, match="snapshots_page_size"):
        load_configuration()


def test_rate_limited_pause_above_max_pause_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CP_POLLER_RATE_LIMITED_PAUSE_SECONDS", "120")

    with pytest.raises(ValidationError, match="rate_limited_pause_seconds"):
        load_configuration()
