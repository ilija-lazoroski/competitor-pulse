import pytest
from pydantic import SecretStr

from competitor_pulse.configuration import DatabaseConfiguration
from competitor_pulse.database import Database, to_sqlalchemy_url
from tests.conftest import DATABASE_URL


def test_url_uses_the_psycopg_driver():
    url = to_sqlalchemy_url(SecretStr(DATABASE_URL))

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "localhost"
    assert url.database == "competitor_pulse"


def test_url_hides_the_password_when_printed():
    assert "postgres:postgres" not in str(to_sqlalchemy_url(SecretStr(DATABASE_URL)))


@pytest.mark.anyio
async def test_database_opens_and_closes_without_a_server():
    # Opening must not wait for a connection (the API starts with the database down).
    database = Database.from_configuration(DatabaseConfiguration())  # type: ignore[call-arg]

    await database.open()
    await database.close()
