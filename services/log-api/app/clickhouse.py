"""ClickHouse client."""
import os
import httpx

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = os.getenv("CLICKHOUSE_PORT", "8123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "logs")

BASE_URL = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}"


async def query(sql: str, params: dict = None) -> list[dict]:
    """Execute a SELECT query and return results as list of dicts."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{BASE_URL}/",
            params={"database": CLICKHOUSE_DATABASE, "default_format": "JSONEachRow"},
            data=sql,
        )
        response.raise_for_status()
        lines = response.text.strip().split("\n")
        import json
        return [json.loads(line) for line in lines if line.strip()]


async def execute(sql: str):
    """Execute a non-SELECT statement."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{BASE_URL}/",
            params={"database": CLICKHOUSE_DATABASE},
            data=sql,
        )
        response.raise_for_status()
        return response.text
