from __future__ import annotations

from db_tool.config.models import ConnectionProfile, ConnectorType, Settings
from db_tool.connectors.base import AbstractConnector


def get_connector(profile: ConnectionProfile, settings: Settings) -> AbstractConnector:
    if profile.type == ConnectorType.MONGODB:
        from db_tool.connectors.mongodb import MongoDBConnector
        return MongoDBConnector(profile, settings)
    if profile.type == ConnectorType.BIGQUERY:
        from db_tool.connectors.bigquery import BigQueryConnector
        return BigQueryConnector(profile, settings)
    if profile.type == ConnectorType.MYSQL:
        from db_tool.connectors.mysql import MySQLConnector
        return MySQLConnector(profile, settings)
    from db_tool.i18n import t
    raise ValueError(t("connector.error.unsupported_type", type=profile.type))
