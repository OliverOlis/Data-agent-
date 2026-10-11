"""SQLite schema and deterministic demo data for the e-commerce MVP."""

from .schema import SCHEMA_SQL, create_schema
from .seed import DEMO_DATA_VERSION, seed_demo_data, create_demo_database

__all__ = [
    "SCHEMA_SQL",
    "create_schema",
    "DEMO_DATA_VERSION",
    "seed_demo_data",
    "create_demo_database",
]
