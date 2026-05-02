"""
Integration tests require real database connections.
Run with: pytest -m integration

Required environment variables:
  MONGO_URI_TEST  - MongoDB connection string for test database
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires real database connections")


@pytest.fixture(scope="session")
def mongo_uri():
    uri = os.environ.get("MONGO_URI_TEST", "mongodb://localhost:27017/db_tool_test")
    return uri
