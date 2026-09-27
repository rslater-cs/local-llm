"""PySide6 system-tray controller for the Local LLM Compose stack."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QCursor, QDesktopServices, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QPlainTextEdit, QSystemTrayIcon, QVBoxLayout

from .compose import CommandResult, ComposeManager
from .config import AppConfig
from .models import Model, ModelManager
from .status import StackStatus, StatusReport


STATUS_LABELS = {
    StackStatus.STOPPED: "○ Stopped", StackStatus.STARTING: "◐ Starting", StackStatus.RUNNING: "● Running",
    StackStatus.READY: "● Ready", StackStatus.UNHEALTHY: "⚠ Unhealthy", StackStatus.ERROR: "✕ Error",
}


def tray_icon() -> QIcon:
    """Render the project-owned SVG before handing it to the system tray."""
    logo_path = Path(__file__).parent / "resources/icons/local-llm.svg"
    renderer = QSvgRenderer(str(logo_path))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class Worker(QThread):
    finished = Signal(object)

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation

    def run(self) -> None:
        try:
            self.finished.emit(self.operation())
        except Exception as error:  # UI feedback must survive operational errors.
            self.finished.emit(error)


class TrayController:
    def __init__(self, app: QApplication, config: AppConfig) -> None:
        self.app, self.config = app, config
        self.logger = self._logger()
        self.compose, self.models = ComposeManager(config, self.logger), ModelManager(config)
        self.busy = False
        self.menu_anchor = QPoint()
        self.last_status = StatusReport(StackStatus.STOPPED)
        self.tray = QSystemTrayIcon(tray_icon(), app)
        self.menu = QMenu()
        # Cinnamon positions Qt's native context menu itself. Leaving this unset
        # lets the activation handler place the menu above the panel icon.
        self.tray.setContextMenu(None)
        self.tray.activated.connect(self._activated)
        self.timer = QTimer(app)
        self.timer.setInterval(5_000)
        self.timer.timeout.connect(self.refresh_status)
        self.rebuild_menu()
        self.tray.show()
        self.timer.start()
        self.refresh_status()

    def _logger(self) -> logging.Logger:
        logger = logging.getLogger("local_llm_tray")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.FileHandler(self.config.app_log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
        logger.info("Application started")
        return logger

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.Context}:
            self.menu_anchor = QCursor.pos()
            self._show_menu_above_tray_icon()

    def _show_menu_above_tray_icon(self) -> None:
        """Place the menu above a bottom-panel icon, as desktop tray menus do."""
        self.menu.ensurePolished()
        self.menu.adjustSize()
        target = self._menu_position()
        self.menu.popup(target)
        # Cinnamon may apply native placement while mapping a popup. Reapply the
        # position after mapping, when QMenu has its final decorated size.
        QTimer.singleShot(0, self._recenter_open_menu)
        QTimer.singleShot(30, self._recenter_open_menu)

    def _menu_position(self) -> QPoint:
        icon_rect = self.tray.geometry()
        menu_size = self.menu.size() if self.menu.isVisible() else self.menu.sizeHint()
        has_icon_geometry = icon_rect.isValid() and not icon_rect.isEmpty()
        anchor = icon_rect.center() if has_icon_geometry else self.menu_anchor
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        x = anchor.x() - menu_size.width() // 2
        x = max(available.left(), min(x, available.right() - menu_size.width() + 1))
        if anchor.y() >= available.center().y():
            icon_top = icon_rect.top() if has_icon_geometry else anchor.y() - 4
            y = min(icon_top - menu_size.height(), available.bottom() - menu_size.height() + 1)
        else:
            icon_bottom = icon_rect.bottom() if has_icon_geometry else anchor.y() + 4
            y = max(icon_bottom + 1, available.top())
        return QPoint(x, y)

    def _recenter_open_menu(self) -> None:
        if not self.menu.isVisible():
            return
        target = self._menu_position()
        self.menu.move(target)
        self.logger.info(
            "Tray menu positioned: icon=%s anchor=%s menu=%sx%s target=%s actual=%s",
            self.tray.geometry(), self.menu_anchor, self.menu.width(), self.menu.height(), target, self.menu.pos(),
        )

    def rebuild_menu(self) -> None:
        self.menu.clear()
        status_action = self.menu.addAction(STATUS_LABELS[self.last_status.status])
        status_action.setEnabled(False)
        if self.last_status.detail:
            status_action.setToolTip(self.last_status.detail)
        model_menu = self.menu.addMenu("Model")
        current = self.models.current_relative_path()
        available = self.models.scan()
        if not available:
            empty = model_menu.addAction("No GGUF models found")
            empty.setEnabled(False)
        for model in available:
            action = model_menu.addAction(model.display_name)
            action.setCheckable(True)
            action.setChecked(model.relative_path == current)
            action.setToolTip(f"{model.relative_path} ({model.file_size / (1024 ** 3):.1f} GiB)")
            action.triggered.connect(lambda checked=False, candidate=model: self.select_model(candidate))
        self.menu.addSeparator()
        start = self.menu.addAction("Start")
        start.setEnabled(not self.busy and self.last_status.status in {StackStatus.STOPPED, StackStatus.ERROR, StackStatus.UNHEALTHY})
        start.triggered.connect(lambda: self.run_operation("Starting Local LLM", self.compose.start))
        stop = self.menu.addAction("Stop")
        stop.setEnabled(not self.busy and self.last_status.status not in {StackStatus.STOPPED, StackStatus.ERROR})
        stop.triggered.connect(lambda: self.run_operation("Stopping Local LLM", self.compose.stop))
        restart = self.menu.addAction("Restart")
        restart.setEnabled(not self.busy and self.last_status.status not in {StackStatus.STOPPED, StackStatus.ERROR})
        restart.triggered.connect(lambda: self.run_operation("Restarting Local LLM", self.compose.restart))
        open_webui = self.menu.addAction("Open WebUI")
        open_webui.setEnabled(not self.busy and self.last_status.status in {StackStatus.RUNNING, StackStatus.READY})
        open_webui.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(self.config.webui_url)))
        self.menu.addSeparator()
        logs = self.menu.addAction("View Logs")
        logs.setEnabled(not self.busy)
        logs.triggered.connect(lambda: self.run_operation("Loading logs", self.compose.get_logs, self.show_logs))
        folder = self.menu.addAction("Open Project Folder")
        folder.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.project_dir))))
        self.menu.addSeparator()
        quit_action = self.menu.addAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        self.tray.setToolTip(f"Local LLM — {STATUS_LABELS[self.last_status.status]}")

    def refresh_status(self) -> None:
        if not self.busy:
            self.run_operation("Checking Local LLM status", self.compose.get_status, quiet=True)

    def select_model(self, model: Model) -> None:
        def operation() -> CommandResult:
            self.models.set_active_model(model)
            self.logger.info("Model selected: %s", model.relative_path)
            return self.compose.apply_configuration()
        self.run_operation(f"Switching to {model.display_name}", operation)

    def run_operation(self, title: str, operation: Callable[[], object], callback: Callable[[object], None] | None = None, quiet: bool = False) -> None:
        if self.busy:
            return
        self.busy = True
        self.last_status = StatusReport(StackStatus.STARTING, title)
        self.rebuild_menu()
        worker = Worker(operation)
        worker.finished.connect(lambda result: self.operation_done(title, result, callback, quiet, worker))
        worker.start()

    def operation_done(self, title: str, result: object, callback: Callable[[object], None] | None, quiet: bool, worker: Worker) -> None:
        worker.deleteLater()
        self.busy = False
        if isinstance(result, Exception):
            self.last_status = StatusReport(StackStatus.ERROR, str(result))
            if not quiet:
                self.notify_error(title, str(result))
        elif isinstance(result, CommandResult) and not result.ok:
            self.last_status = StatusReport(StackStatus.ERROR, result.message)
            if not quiet:
                self.notify_error(title, result.message)
        elif isinstance(result, StatusReport):
            self.last_status = result
        else:
            if callback:
                callback(result)
            # Never run a Docker command on the Qt event loop. The timer invokes
            # a worker-backed refresh after a lifecycle command completes.
            QTimer.singleShot(0, self.refresh_status)
        self.rebuild_menu()

    def notify_error(self, title: str, detail: str) -> None:
        self.logger.error("%s: %s", title, detail)
        self.tray.showMessage(title, detail, QSystemTrayIcon.MessageIcon.Critical)

    def show_logs(self, result: object) -> None:
        if not isinstance(result, CommandResult):
            return
        dialog = QDialog()
        dialog.setWindowTitle("Local LLM service logs")
        dialog.resize(850, 550)
        output = QPlainTextEdit(result.stdout or "No logs available.")
        output.setReadOnly(True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(output)
        dialog.show()
        self._log_dialog = dialog


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = AppConfig.discover()
    errors = config.validate()
    if errors:
        QMessageBox.critical(None, "Local LLM configuration", "\n".join(errors))
        return 2
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, "Local LLM", "No system tray is available. On GNOME, enable an AppIndicator/StatusNotifier extension.")
    TrayController(app, config)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
