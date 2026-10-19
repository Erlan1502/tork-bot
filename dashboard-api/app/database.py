import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from typing import Generator
import time
import logging
from app.config import settings

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None

def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        max_retries = 10
        for i in range(max_retries):
            try:
                _pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    host=settings.POSTGRES_HOST,
                    port=settings.POSTGRES_PORT,
                    dbname=settings.POSTGRES_DB,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                )
                logger.info("PostgreSQL connection pool created successfully.")
                break
            except Exception as e:
                logger.warning(f"Waiting for database ({i+1}/{max_retries})... Error: {e}")
                time.sleep(2)
        if _pool is None:
            raise RuntimeError("Could not connect to PostgreSQL database.")
    return _pool

@contextmanager
def get_db_cursor() -> Generator[RealDictCursor, None, None]:
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)

def get_db():
    with get_db_cursor() as cur:
        yield cur
