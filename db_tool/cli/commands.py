from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from db_tool.cli.formatters import (
    confirm_copy_without_obfuscation,
    confirm_stage_operation,
    console,
    print_operation_result,
    print_profiles,
    print_progress,
)
from db_tool.config.loader import ConfigError, ConfigLoader
from db_tool.config.models import ConnectorType, Environment
from db_tool.config.validator import ProductionMutationError, ProductionWriteError, requires_stage_confirmation
from db_tool.connectors import get_connector
from db_tool.i18n import t

app = typer.Typer(name="db-tool", help=t("cli.app.help"))


@app.callback(invoke_without_command=True)
def _global_options(
    debug: bool = typer.Option(False, "--debug", is_eager=True, help=t("cli.tui.option.debug")),
) -> None:
    from db_tool.logging_config import setup_logging
    setup_logging(debug=debug)


_loader: ConfigLoader | None = None


def _get_loader() -> ConfigLoader:
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
        _warn_connection_strings(_loader)
    return _loader


def _warn_connection_strings(loader: ConfigLoader) -> None:
    try:
        loader.load_profiles()
        for w in loader.get_connection_warnings():
            from db_tool.i18n import t
            msg = t(
                "validator.warning.connection_string_mismatch",
                alias=w.alias,
                declared=w.declared_env.value,
                detected=w.detected_env.value,
                keyword=w.matched_keyword,
                severity=w.severity.upper(),
            )
            color = typer.colors.RED if w.severity == "high" else typer.colors.YELLOW
            typer.echo(typer.style(f"WARNING: {msg}", fg=color), err=True)
    except Exception:
        pass


def _get_settings():
    return _get_loader().load_settings()


def _build_engine(settings):
    from db_tool.obfuscation.engine import ObfuscationEngine
    return ObfuscationEngine(settings)


# ── copy ──────────────────────────────────────────────────────────────────────

@app.command(help=t("cli.copy.help"))
def copy(
    source: str = typer.Option(..., "--source", "-s", help=t("cli.copy.option.source")),
    target: str = typer.Option(..., "--target", "-t", help=t("cli.copy.option.target")),
    pattern: str = typer.Option(".*", "--pattern", "-p", help=t("cli.copy.option.pattern")),
    obfuscate: bool = typer.Option(False, "--obfuscate", help=t("cli.copy.option.obfuscate")),
    data_only: bool = typer.Option(False, "--data-only", help=t("cli.copy.option.data_only")),
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli.copy.option.dry_run")),
    resume: bool = typer.Option(False, "--resume", help=t("cli.copy.option.resume")),
    max_docs: int = typer.Option(0, "--max-docs", help=t("cli.copy.option.max_docs")),
):
    from db_tool.operations.copy import run_copy

    settings = _get_settings()
    try:
        src_profile = _get_loader().get_profile(source)
        tgt_profile = _get_loader().get_profile(target)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if tgt_profile.is_production:
        typer.echo(t("cli.error.production_write", target=target), err=True)
        raise typer.Exit(1)

    if requires_stage_confirmation(tgt_profile):
        if not confirm_stage_operation(target, "copy"):
            raise typer.Abort()

    if src_profile.is_production and not obfuscate:
        if not confirm_copy_without_obfuscation(source):
            raise typer.Abort()

    engine = _build_engine(settings) if obfuscate else None

    with get_connector(src_profile, settings) as src, get_connector(tgt_profile, settings) as tgt:
        result = run_copy(
            source=src,
            target=tgt,
            pattern=pattern,
            settings=settings,
            obfuscation_engine=engine,
            data_only=data_only,
            dry_run=dry_run,
            resume=resume,
            max_docs_per_collection=max_docs,
            progress_callback=print_progress,
        )
    print_operation_result(result)


# ── sync ──────────────────────────────────────────────────────────────────────

@app.command(help=t("cli.sync.help"))
def sync(
    source: str = typer.Option(..., "--source", "-s"),
    target: str = typer.Option(..., "--target", "-t"),
    pattern: str = typer.Option(".*", "--pattern", "-p"),
    obfuscate: bool = typer.Option(False, "--obfuscate"),
):
    from db_tool.operations.sync import run_sync

    settings = _get_settings()
    try:
        src_profile = _get_loader().get_profile(source)
        tgt_profile = _get_loader().get_profile(target)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if tgt_profile.is_production:
        typer.echo(t("cli.error.production_write", target=target), err=True)
        raise typer.Exit(1)

    if requires_stage_confirmation(tgt_profile):
        if not confirm_stage_operation(target, "sync"):
            raise typer.Abort()

    if src_profile.is_production and not obfuscate:
        if not confirm_copy_without_obfuscation(source):
            raise typer.Abort()

    engine = _build_engine(settings) if obfuscate else None

    with get_connector(src_profile, settings) as src, get_connector(tgt_profile, settings) as tgt:
        result = run_sync(src, tgt, pattern, settings, obfuscation_engine=engine, progress_callback=print_progress)
    print_operation_result(result)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command(help=t("cli.delete.help"))
def delete(
    target: str = typer.Option(..., "--target", "-t"),
    pattern: str = typer.Option(..., "--pattern", "-p", help=t("cli.copy.option.pattern")),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    from db_tool.operations.delete import run_delete

    settings = _get_settings()
    try:
        tgt_profile = _get_loader().get_profile(target)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if tgt_profile.is_production:
        typer.echo(t("cli.error.production_write", target=target), err=True)
        raise typer.Exit(1)

    if requires_stage_confirmation(tgt_profile):
        if not confirm_stage_operation(target, "delete"):
            raise typer.Abort()

    with get_connector(tgt_profile, settings) as tgt:
        result = run_delete(tgt, pattern, settings, dry_run=dry_run, progress_callback=print_progress)
    print_operation_result(result)


# ── obfuscate ─────────────────────────────────────────────────────────────────

@app.command(help=t("cli.obfuscate.help"))
def obfuscate(
    target: str = typer.Option(..., "--target", "-t"),
    pattern: str = typer.Option(".*", "--pattern", "-p"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    from db_tool.operations.obfuscate import run_obfuscate

    settings = _get_settings()
    try:
        tgt_profile = _get_loader().get_profile(target)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if tgt_profile.is_production:
        typer.echo(t("cli.error.production_obfuscate", target=target), err=True)
        raise typer.Exit(1)

    if requires_stage_confirmation(tgt_profile):
        if not confirm_stage_operation(target, "obfuscate-in-place"):
            raise typer.Abort()

    engine = _build_engine(settings)
    with get_connector(tgt_profile, settings) as tgt:
        result = run_obfuscate(tgt, pattern, engine, settings, dry_run=dry_run, progress_callback=print_progress)
    print_operation_result(result)


# ── export ────────────────────────────────────────────────────────────────────

@app.command(help=t("cli.export.help"))
def export(
    source: str = typer.Option(..., "--source", "-s"),
    pattern: str = typer.Option(".*", "--pattern", "-p"),
    output: Path = typer.Option(Path("."), "--output", "-o", help=t("cli.export.option.output")),
    obfuscate_flag: bool = typer.Option(False, "--obfuscate"),
):
    from db_tool.operations.export import run_export

    settings = _get_settings()
    try:
        src_profile = _get_loader().get_profile(source)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if src_profile.is_production and not obfuscate_flag:
        if not confirm_copy_without_obfuscation(source):
            raise typer.Abort()

    engine = _build_engine(settings) if obfuscate_flag else None

    with get_connector(src_profile, settings) as src:
        result = run_export(src, pattern, output, settings, obfuscation_engine=engine, progress_callback=print_progress)
    print_operation_result(result)


# ── config ────────────────────────────────────────────────────────────────────

config_app = typer.Typer(help=t("cli.config.help"))
app.add_typer(config_app, name="config")


@config_app.command("list", help=t("cli.config.list.help"))
def config_list():
    try:
        profiles = _get_loader().load_profiles()
        print_profiles(profiles)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)


@config_app.command("add", help=t("cli.config.add.help"))
def config_add(
    alias: str = typer.Option(..., prompt=True),
    environment: str = typer.Option(..., prompt=True, help=t("cli.config.add.option.environment")),
    db_type: str = typer.Option(..., prompt=True, help=t("cli.config.add.option.db_type")),
    connection_string: str = typer.Option(..., prompt=True, hide_input=True),
    database_name: str = typer.Option(..., prompt=True, help=t("cli.config.add.option.database_name")),
):
    from db_tool.config.models import ConnectionProfile, ConnectorType, Environment
    try:
        profile = ConnectionProfile(
            alias=alias,
            environment=Environment(environment),
            type=ConnectorType(db_type),
            connection_string=connection_string,
            database_name=database_name,
        )
        _get_loader().add_profile(profile)
        console.print(f"[green]{t('cli.success.connection_added', alias=alias)}[/green]")
    except (ConfigError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)


@config_app.command("remove", help=t("cli.config.remove.help"))
def config_remove(alias: str = typer.Argument(...)):
    try:
        _get_loader().remove_profile(alias)
        console.print(f"[green]{t('cli.success.connection_removed', alias=alias)}[/green]")
    except (ConfigError, ProductionMutationError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)


@config_app.command("test", help=t("cli.config.test.help"))
def config_test(alias: str = typer.Argument(...)):
    settings = _get_settings()
    try:
        profile = _get_loader().get_profile(alias)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    console.print(t("cli.config.test.testing", alias=alias))
    try:
        with get_connector(profile, settings) as conn:
            collections = conn.list_collections()
        console.print(f"[green]{t('cli.success.connection_test_ok', count=len(collections))}[/green]")
    except Exception as exc:
        typer.echo(t("cli.error.failed", exc=exc), err=True)
        raise typer.Exit(1)


# ── cleanup ───────────────────────────────────────────────────────────────────

cleanup_app = typer.Typer(help=t("cli.cleanup.help"))
app.add_typer(cleanup_app, name="cleanup")


@cleanup_app.command("mappings", help=t("cli.cleanup.mappings.help"))
def cleanup_mappings():
    from db_tool.obfuscation.mappings import MappingStore
    settings = _get_settings()
    store = MappingStore(settings)
    count = store.clear_all()
    console.print(f"[green]{t('cli.success.mappings_deleted', count=count)}[/green]")


@cleanup_app.command("state", help=t("cli.cleanup.state.help"))
def cleanup_state():
    from db_tool.state.manager import StateManager
    settings = _get_settings()
    manager = StateManager(settings)
    count = manager.clear_all()
    console.print(f"[green]{t('cli.success.state_deleted', count=count)}[/green]")


# ── tui ───────────────────────────────────────────────────────────────────────

@app.command(help=t("cli.tui.help"))
def tui(debug: bool = typer.Option(False, "--debug", help=t("cli.tui.option.debug"))):
    from db_tool.logging_config import setup_logging
    from db_tool.tui.app import DBToolApp
    setup_logging(debug=debug)
    DBToolApp(debug=debug).run()
