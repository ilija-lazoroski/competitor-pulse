import asyncio
from typing import Final

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import SecretStr
from sqlalchemy import NullPool, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from competitor_pulse.configuration import DatabaseConfiguration

CONNECT_TIMEOUT_SECONDS: Final = 5
# How long a query waits for a free connection before it fails.
POOL_TIMEOUT_SECONDS: Final = 10
PING_TIMEOUT_SECONDS: Final = 5


def to_sqlalchemy_url(database_url: SecretStr) -> URL:
    """postgresql://… URLs need the psycopg (v3) driver name for SQLAlchemy."""
    return make_url(database_url.get_secret_value()).set(drivername="postgresql+psycopg")


class Database:
    """SQLAlchemy Core on top of a psycopg connection pool.

    SQLAlchemy's own pooling is off (NullPool): every connection comes from the psycopg pool,
    and close_returns=True makes SQLAlchemy's close() hand the connection back to that pool
    instead of closing it.
    """

    def __init__(self, pool: AsyncConnectionPool[AsyncConnection], engine: AsyncEngine):
        self._pool = pool
        self._engine = engine

    @classmethod
    def from_configuration(cls, config: DatabaseConfiguration) -> "Database":
        pool = AsyncConnectionPool(
            config.url.get_secret_value(),
            min_size=config.pool_min_size,
            max_size=config.pool_max_size,
            kwargs={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
            check=AsyncConnectionPool.check_connection,
            timeout=POOL_TIMEOUT_SECONDS,
            close_returns=True,
            open=False,
        )
        engine = create_async_engine(
            "postgresql+psycopg://", poolclass=NullPool, async_creator=pool.getconn
        )
        return cls(pool, engine)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def open(self) -> None:
        """Starts the pool without waiting, so the API starts even if the database is down."""
        await self._pool.open(wait=False)

    async def ping(self) -> None:
        """Runs SELECT 1; raises if the database cannot be reached in time."""
        async with asyncio.timeout(PING_TIMEOUT_SECONDS):
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
        await self._pool.close()
