from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.markup import escape as markup_escape
from textual.app import ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Log, ProgressBar, Rule

from db_tool.i18n import t

_log = logging.getLogger("db_tool.tui.progress")

if TYPE_CHECKING:
    from db_tool.config.loader import ConfigLoader
    from db_tool.config.models import Settings
    from db_tool.tui.screens.operation_config import OperationConfig


# ── Messages posted from the worker thread (non-blocking) ────────────────────

class StatusUpdate(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class OperationProgress(Message):
    def __init__(self, event: Any) -> None:
        super().__init__()
        self.event = event


class OperationError(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class OperationDone(Message):
    pass


# ── Screen ───────────────────────────────────────────────────────────────────

class ProgressScreen(Screen[None]):
    """Shows live progress for a running operation."""

    BINDINGS = [("escape", "go_back", t("tui.progress.binding.back"))]

    async def _pre_process(self) -> bool:
        _log.debug("_pre_process started")
        result = await super()._pre_process()
        _log.debug(f"_pre_process finished: result={result}")
        return result

    async def _process_messages(self) -> None:
        _log.debug("_process_messages started")
        await super()._process_messages()
        _log.debug("_process_messages finished")

    def __init__(
        self,
        operation: str,
        config: "OperationConfig",
        loader: "ConfigLoader",
        settings: "Settings",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._operation = operation
        self._config = config
        self._loader = loader
        self._settings = settings
        self._error_count = 0

    def compose(self) -> ComposeResult:
        _log.debug("compose called")
        yield Header()
        yield Label(t("tui.progress.title", operation=self._operation.upper()), id="title")
        yield Rule()
        yield ProgressBar(total=100, id="progress_bar", show_eta=False)
        yield Label("", id="collection_label")
        yield Label(t("tui.progress.status.initializing"), id="status_label")
        yield Rule()
        yield Log(id="log", highlight=True)
        yield Footer()
        _log.debug("compose finished")

    def on_mount(self) -> None:
        _log.debug("on_mount — starting worker thread")
        self.run_worker(self._run_operation, thread=True)
        _log.debug("on_mount — worker started")

    # ── Worker (runs in background thread) ───────────────────────────────────

    def _run_operation(self) -> None:
        _log.debug("worker _run_operation started")
        try:
            self._execute()
            _log.debug("worker _execute completed normally")
        except Exception as exc:
            _log.debug(f"_execute raised: {exc!r}")
            self.post_message(OperationError(markup_escape(str(exc))))
        finally:
            _log.debug("worker posting OperationDone")
            self.post_message(OperationDone())

    def _notify(self, msg: str) -> None:
        _log.debug(f"status: {msg!r}")
        self.post_message(StatusUpdate(msg))

    def _execute(self) -> None:
        from db_tool.connectors import get_connector
        from db_tool.tui.screens.operation_config import OperationConfig

        config = self._config
        _log.debug(f"_execute: op={self._operation!r}, config={config!r}")
        if not isinstance(config, OperationConfig):
            _log.debug("worker _execute: config not OperationConfig, returning")
            return

        try:
            src_profile = self._loader.get_profile(config.source_alias) if config.source_alias else None
            tgt_profile = self._loader.get_profile(config.target_alias) if config.target_alias else None
            _log.debug(f"profiles resolved: src={src_profile and src_profile.alias!r}, tgt={tgt_profile and tgt_profile.alias!r}")
        except Exception as exc:
            _log.debug(f"profile resolution failed: {exc!r}")
            raise RuntimeError(str(exc)) from exc

        engine = None
        if config.obfuscate:
            from db_tool.obfuscation.engine import ObfuscationEngine
            engine = ObfuscationEngine(self._settings)

        def callback(event: object) -> None:
            self.post_message(OperationProgress(event))

        op = self._operation
        _log.debug(f"dispatching op={op!r}")
        if op == "copy" and src_profile and tgt_profile:
            from db_tool.operations.copy import run_copy
            self._notify(t("tui.progress.status.connecting", alias=src_profile.alias))
            with get_connector(src_profile, self._settings) as src:
                self._notify(t("tui.progress.status.connecting", alias=tgt_profile.alias))
                with get_connector(tgt_profile, self._settings) as tgt:
                    self._notify(t("tui.progress.status.starting"))
                    run_copy(src, tgt, config.pattern, self._settings,
                             obfuscation_engine=engine, data_only=config.data_only,
                             dry_run=config.dry_run, resume=config.resume,
                             max_docs_per_collection=config.max_docs,
                             progress_callback=callback)
        elif op == "sync" and src_profile and tgt_profile:
            from db_tool.operations.sync import run_sync
            self._notify(t("tui.progress.status.connecting", alias=src_profile.alias))
            with get_connector(src_profile, self._settings) as src:
                self._notify(t("tui.progress.status.connecting", alias=tgt_profile.alias))
                with get_connector(tgt_profile, self._settings) as tgt:
                    self._notify(t("tui.progress.status.starting"))
                    run_sync(src, tgt, config.pattern, self._settings,
                             obfuscation_engine=engine, progress_callback=callback)
        elif op == "delete" and tgt_profile:
            from db_tool.operations.delete import run_delete
            self._notify(t("tui.progress.status.connecting", alias=tgt_profile.alias))
            with get_connector(tgt_profile, self._settings) as tgt:
                self._notify(t("tui.progress.status.starting"))
                run_delete(tgt, config.pattern, self._settings,
                           dry_run=config.dry_run, progress_callback=callback)
        elif op == "obfuscate" and tgt_profile:
            from db_tool.operations.obfuscate import run_obfuscate
            self._notify(t("tui.progress.status.connecting", alias=tgt_profile.alias))
            with get_connector(tgt_profile, self._settings) as tgt:
                self._notify(t("tui.progress.status.starting"))
                run_obfuscate(tgt, config.pattern, engine, self._settings,
                              dry_run=config.dry_run, progress_callback=callback)
        elif op == "export" and src_profile:
            from pathlib import Path
            from db_tool.operations.export import run_export
            self._notify(t("tui.progress.status.connecting", alias=src_profile.alias))
            with get_connector(src_profile, self._settings) as src:
                self._notify(t("tui.progress.status.starting"))
                run_export(src, config.pattern, Path("."), self._settings,
                           obfuscation_engine=engine, progress_callback=callback)

    # ── Message handlers (run in event loop) ─────────────────────────────────

    def on_status_update(self, message: StatusUpdate) -> None:
        safe = markup_escape(message.text)
        self.query_one("#status_label", Label).update(safe)
        self.query_one("#log", Log).write_line(safe)

    def on_operation_progress(self, message: OperationProgress) -> None:
        from db_tool.operations import ProgressEvent
        event = message.event
        if not isinstance(event, ProgressEvent):
            return

        if event.error:
            self._error_count += 1

        col_total = max(event.collections_total, 1)
        doc_total = max(event.docs_total, 1)
        global_pct = ((event.collection_index + event.docs_processed / doc_total) / col_total) * 100

        collection_label = t(
            "tui.progress.collection_counter",
            current=event.collection_index + 1,
            total=col_total,
            collection=event.collection,
        )
        log_line = t(
            "tui.progress.log.batch",
            phase=event.phase,
            collection=event.collection,
            batch_index=event.batch_index,
            docs_processed=event.docs_processed,
            docs_total=event.docs_total,
        )
        if event.upserted or event.modified:
            log_line += t("tui.progress.log.new_updated", upserted=event.upserted, modified=event.modified)
        if event.obfuscated:
            log_line += t("tui.progress.log.obfuscated", obfuscated=event.obfuscated)
        if event.skipped:
            log_line += t("tui.progress.log.skipped", skipped=event.skipped)
        if event.error:
            log_line += t("tui.progress.log.error", error=event.error)

        self.query_one("#progress_bar", ProgressBar).progress = global_pct
        self.query_one("#collection_label", Label).update(collection_label)
        self.query_one("#status_label", Label).update(markup_escape(log_line))
        self.query_one("#log", Log).write_line(log_line)

    def on_operation_error(self, message: OperationError) -> None:
        self.query_one("#status_label", Label).add_class("error")
        safe = markup_escape(message.text)
        self.query_one("#status_label", Label).update(t("tui.progress.status.error", message=safe))
        self.query_one("#log", Log).write_line(t("tui.progress.status.error", message=safe))

    def on_operation_done(self, _message: OperationDone) -> None:
        _log.debug(f"on_operation_done — errors={self._error_count}")
        self._running = False
        done_msg = t("tui.progress.status.done")
        if self._error_count:
            done_msg += t("tui.progress.status.done_with_errors", count=self._error_count)
        self.query_one("#status_label", Label).update(done_msg)
        self.query_one("#progress_bar", ProgressBar).progress = 100

    # ── Kept for backward compat (called nowhere now) ─────────────────────

    def update_status(self, message: str) -> None:
        safe = markup_escape(message)
        self.query_one("#status_label", Label).update(safe)
        self.query_one("#log", Log).write_line(safe)

    def action_go_back(self) -> None:
        _log.debug(f"action_go_back — running={self._running}")
        if self._running:
            for worker in self.workers:
                worker.cancel()
            self._running = False
        self.dismiss()
