from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from db_tool.config.models import ConnectionProfile, Environment
from db_tool.i18n import t
from db_tool.operations import OperationResult

console = Console()
err_console = Console(stderr=True)


def print_profiles(profiles: list[ConnectionProfile]) -> None:
    table = Table(title=t("cli.formatter.table.connections"), show_header=True)
    table.add_column(t("cli.formatter.table.alias"), style="bold cyan")
    table.add_column(t("cli.formatter.table.environment"))
    table.add_column(t("cli.formatter.table.type"))
    table.add_column(t("cli.formatter.table.blacklist"))
    for p in profiles:
        env_style = "red" if p.is_production else "yellow" if p.is_stage else "green"
        table.add_row(
            p.alias,
            f"[{env_style}]{p.environment.value}[/{env_style}]",
            p.type.value,
            ", ".join(p.blacklist) if p.blacklist else "—",
        )
    console.print(table)


def print_operation_result(result: OperationResult) -> None:
    table = Table(title=t("cli.formatter.table.operation", operation=result.operation), show_header=True)
    table.add_column(t("cli.formatter.table.collection"), style="bold")
    table.add_column(t("cli.formatter.table.upserted"), justify="right")
    table.add_column(t("cli.formatter.table.modified"), justify="right")
    table.add_column(t("cli.formatter.table.skipped"), justify="right")
    table.add_column(t("cli.formatter.table.status"))
    for col in result.collections:
        status = t("cli.formatter.status.error") if col.error else t("cli.formatter.status.ok")
        table.add_row(
            col.collection,
            str(col.upserted),
            str(col.modified),
            str(col.skipped),
            status,
        )
    console.print(table)
    console.print(t(
        "cli.formatter.summary",
        total_upserted=result.total_upserted,
        total_modified=result.total_modified,
        total_skipped=result.total_skipped,
        elapsed=result.elapsed_seconds,
    ))


def confirm_stage_operation(alias: str, operation: str) -> bool:
    return typer.confirm(
        t("cli.formatter.confirm.stage", alias=alias, operation=operation),
        default=False,
    )


def confirm_copy_without_obfuscation(source_alias: str) -> bool:
    return typer.confirm(
        t("cli.formatter.confirm.production_copy", source_alias=source_alias),
        default=False,
    )


def print_progress(event: object) -> None:
    from db_tool.operations import ProgressEvent
    if not isinstance(event, ProgressEvent):
        return
    if event.phase == "complete":
        console.print(t(
            "cli.formatter.progress.complete",
            collection=event.collection,
            upserted=event.upserted,
            modified=event.modified,
            skipped=event.skipped,
        ))
    elif event.phase == "error":
        err_console.print(t("cli.formatter.progress.error", collection=event.collection, error=event.error))
