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
