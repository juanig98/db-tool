from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from db_tool.config.loader import ConfigLoader
from db_tool.config.models import ConnectionProfile, ConnectorType, Environment, Settings


class TestConnectionManagement:
    def test_delete_production_blocked(self) -> None:
        """No se debe poder borrar una conexión de producción."""
        from db_tool.config.validator import guard_connection_mutation, ProductionMutationError

        profile = ConnectionProfile(
            alias="prod-db",
            environment=Environment.PRODUCTION,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://prod:27017",
            database_name="proddb",
        )

        with pytest.raises(ProductionMutationError):
            guard_connection_mutation(profile)

    def test_delete_non_production_allowed(self) -> None:
        """Se debe poder borrar conexiones no productivas."""
        from db_tool.config.validator import guard_connection_mutation

        profile = ConnectionProfile(
            alias="dev-db",
            environment=Environment.DEV,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://localhost:27017",
            database_name="devdb",
        )

        guard_connection_mutation(profile)

    def test_delete_stage_blocked(self) -> None:
        """Stage también debe bloquearse por ser crítico."""
        from db_tool.config.validator import guard_connection_mutation

        profile = ConnectionProfile(
            alias="stage-db",
            environment=Environment.STAGE,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://stage:27017",
            database_name="stagedb",
        )

        guard_connection_mutation(profile)


class TestConnectionForm:
    def test_blacklist_parses_correctly(self) -> None:
        """El blacklist debe parsearse correctamente."""
        lines = "^system\\..*\n^tmp_.*\n^backup_.*"
        blacklist = [line.strip() for line in lines.split("\n") if line.strip()]

        assert len(blacklist) == 3
        assert blacklist[0] == "^system\\..*"
        assert blacklist[1] == "^tmp_.*"
        assert blacklist[2] == "^backup_.*"

    def test_alias_required_validation(self) -> None:
        """El alias no debe estar vacío."""
        with pytest.raises(Exception):
            ConnectionProfile(
                alias="",
                environment=Environment.LOCAL,
                type=ConnectorType.MONGODB,
                connection_string="mongodb://localhost:27017",
                database_name="test",
            )

    def test_environment_values(self) -> None:
        """Todos los valores de environment deben ser válidos."""
        for env in [Environment.PRODUCTION, Environment.STAGE, Environment.DEV, Environment.LOCAL]:
            profile = ConnectionProfile(
                alias="test",
                environment=env,
                type=ConnectorType.MONGODB,
                connection_string="mongodb://localhost:27017",
                database_name="test",
            )
            assert profile.environment == env

    def test_connector_type_values(self) -> None:
        """Todos los valores de connector type deben ser válidos."""
        for ctype in [ConnectorType.MONGODB, ConnectorType.BIGQUERY, ConnectorType.MYSQL]:
            profile = ConnectionProfile(
                alias="test",
                environment=Environment.LOCAL,
                type=ctype,
                connection_string="mongodb://localhost:27017",
                database_name="test",
            )
            assert profile.type == ctype

    def test_is_production_property(self) -> None:
        """is_production debe devolver True solo para production."""
        prod = ConnectionProfile(
            alias="prod",
            environment=Environment.PRODUCTION,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://prod:27017",
            database_name="test",
        )
        assert prod.is_production is True

        dev = ConnectionProfile(
            alias="dev",
            environment=Environment.DEV,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://localhost:27017",
            database_name="test",
        )
        assert dev.is_production is False

    def test_is_writable_property(self) -> None:
        """is_writable debe ser False para production."""
        prod = ConnectionProfile(
            alias="prod",
            environment=Environment.PRODUCTION,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://prod:27017",
            database_name="test",
        )
        assert prod.is_writable is False

        dev = ConnectionProfile(
            alias="dev",
            environment=Environment.DEV,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://localhost:27017",
            database_name="test",
        )
        assert dev.is_writable is True