from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def make_connections(tmp_path: Path) -> Path:
    f = tmp_path / "connections.yaml"
    f.write_text(yaml.dump([
        {"alias": "dev-db", "environment": "dev", "type": "mongodb",
         "connection_string": "mongodb://localhost", "database_name": "db", "blacklist": []},
    ]))
    return f


@pytest.mark.asyncio
async def test_main_menu_renders(tmp_path):
    from db_tool.config.loader import ConfigLoader
    from db_tool.tui.screens.main_menu import MainMenuScreen
    from textual.app import App

    connections = make_connections(tmp_path)
    loader = ConfigLoader(connections_path=connections, settings_path=tmp_path / "settings.env")
    settings = loader.load_settings()

    class TestApp(App):
        def on_mount(self):
            self.push_screen(MainMenuScreen(loader, settings))

    async with TestApp().run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert screen.query_one("#copy") is not None
        assert screen.query_one("#sync") is not None
        assert screen.query_one("#delete") is not None


@pytest.mark.asyncio
async def test_settings_screen_renders(tmp_path):
    from db_tool.config.loader import ConfigLoader
    from db_tool.config.models import Settings
    from db_tool.tui.screens.settings import SettingsScreen
    from textual.app import App

    connections = make_connections(tmp_path)
    loader = ConfigLoader(connections_path=connections, settings_path=tmp_path / "settings.env")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(SettingsScreen(loader, Settings()))

    async with TestApp().run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert screen.query_one("#batch_size") is not None
        assert screen.query_one("#throttle_rps") is not None


@pytest.mark.asyncio
async def test_cleanup_screen_renders(tmp_path):
    from db_tool.config.models import Settings
    from db_tool.tui.screens.cleanup import CleanupScreen
    from textual.app import App

    settings = Settings(state_dir=tmp_path / "state", mappings_dir=tmp_path / "mappings")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(CleanupScreen(settings))

    async with TestApp().run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert screen.query_one("#clear_mappings") is not None
        assert screen.query_one("#clear_state") is not None


@pytest.mark.asyncio
async def test_operation_config_screen_renders(tmp_path):
    from db_tool.tui.screens.operation_config import OperationConfigScreen
    from textual.app import App

    class TestApp(App):
        def on_mount(self):
            self.push_screen(OperationConfigScreen("copy", "src", "tgt"))

    async with TestApp().run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert screen.query_one("#pattern") is not None
        assert screen.query_one("#dry_run") is not None
        assert screen.query_one("#data_only") is not None
