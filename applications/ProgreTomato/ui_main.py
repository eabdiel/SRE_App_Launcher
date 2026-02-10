from __future__ import annotations

import threading
from pynput import mouse as pynput_mouse

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QObject
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QTableView, QMessageBox, QLineEdit, QMenu, QInputDialog,
    QCheckBox
)
from PySide6.QtWidgets import QHeaderView

from models import Step, AutomationProject
from storage import save_project_json, load_project_json
from export_xlsx import export_project_xlsx
from win_utils import get_foreground_window_info, get_window_info_from_point
from recorder import Recorder, RecorderConfig
from app_state import AppState
from runner import Runner
from responsive_bar import ResponsiveBar


class StepsTableModel(QAbstractTableModel):
    headers = [
        "#", "Channel", "Action", "Window", "Process", "LocatorType", "Locator",
        "InputRef", "Value", "OutputRef", "WaitMs", "Notes"
    ]

    def __init__(self, project: AutomationProject):
        super().__init__()
        self.project = project

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.project.steps)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.headers[section]
        return str(section + 1)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        step = self.project.steps[index.row()]
        col = index.column()

        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == 0: return index.row() + 1
            if col == 1: return step.channel
            if col == 2: return step.action
            if col == 3: return step.window_title
            if col == 4: return step.process_name
            if col == 5: return step.locator_type
            if col == 6: return step.locator
            if col == 7: return step.input_ref
            if col == 8: return step.value
            if col == 9: return step.output_ref
            if col == 10: return step.wait_ms
            if col == 11: return step.notes

        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        editable_cols = {7, 8, 9, 10, 11, 6, 5}
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() in editable_cols:
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False
        step = self.project.steps[index.row()]
        col = index.column()

        try:
            if col == 5: step.locator_type = str(value)
            elif col == 6: step.locator = str(value)
            elif col == 7: step.input_ref = str(value)
            elif col == 8: step.value = str(value)
            elif col == 9: step.output_ref = str(value)
            elif col == 10: step.wait_ms = int(value) if str(value).strip() else 0
            elif col == 11: step.notes = str(value)
            else:
                return False
        except Exception:
            return False

        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        self.project.touch()
        return True

    def add_step(self, step: Step) -> None:
        row = len(self.project.steps)
        self.beginInsertRows(QModelIndex(), row, row)
        self.project.steps.append(step)
        self.endInsertRows()
        self.project.touch()

    def remove_selected(self, rows: list[int]) -> None:
        for r in sorted(rows, reverse=True):
            if 0 <= r < len(self.project.steps):
                self.beginRemoveRows(QModelIndex(), r, r)
                self.project.steps.pop(r)
                self.endRemoveRows()
        self.project.touch()


class RunSignals(QObject):
    status = Signal(str)
    finished = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProgreTomato - Automation Workbench (Windows)")
        self.resize(1200, 720)

        self.state = AppState()
        self.state.project.name = "ProgreTomato"

        self.model = StepsTableModel(self.state.project)
        self.recorder = Recorder(self._on_step_emitted, RecorderConfig(channel="win"))

        self._run_thread = None
        self._stop_run = False
        self._run_signals = RunSignals()
        self._run_signals.status.connect(self._set_status)
        self._run_signals.finished.connect(self._on_run_finished)

        self._step_index = 0
        self._step_lock = threading.Lock()

        # target pick mode
        self._pick_listener = None

        self._build_ui()

    # ----------------------------
    # UI
    # ----------------------------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)

        # Responsive toolbar area
        self.top_bar = ResponsiveBar(max_rows=2)
        main.addWidget(self.top_bar)

        self.project_name = QLineEdit(self.state.project.name)
        self.project_name.setPlaceholderText("Project name")
        self.project_name.textChanged.connect(self._on_project_name_changed)

        self.btn_pick = QPushButton("Pick Target (click next window)")
        self.btn_pick.clicked.connect(self.pick_target_window_next_click)

        self.lbl_target = QLabel("Target: (none)")
        self.lbl_target.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.chk_target_lock = QCheckBox("Target Lock")
        self.chk_target_lock.setChecked(True)

        self.chk_same_process = QCheckBox("Include Same Process Windows")
        self.chk_same_process.setChecked(True)

        self.btn_start = QPushButton("Start Recording")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")

        self.btn_start.clicked.connect(self.start_recording)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(self.stop_recording)

        self.btn_run = QPushButton("Run")
        self.btn_cancel_run = QPushButton("Cancel Run")
        self.btn_run.clicked.connect(self.run_automation)
        self.btn_cancel_run.clicked.connect(self.cancel_run)

        self.btn_step = QPushButton("Step (F10)")
        self.btn_reset_step = QPushButton("Reset Step (F8)")
        self.btn_step.clicked.connect(self.run_single_step)
        self.btn_reset_step.clicked.connect(self.reset_step_pointer)

        self.btn_save = QPushButton("Save JSON")
        self.btn_load = QPushButton("Load JSON")
        self.btn_xlsx = QPushButton("Export XLSX")

        self.btn_save.clicked.connect(self.save_json)
        self.btn_load.clicked.connect(self.load_json)
        self.btn_xlsx.clicked.connect(self.export_xlsx)

        # Put toolbar widgets in a single ordered list; ResponsiveBar will wrap them
        self.top_bar.set_items([
            QLabel("Project:"),
            self.project_name,
            self.btn_pick,
            self.lbl_target,
            self.chk_target_lock,
            self.chk_same_process,
            self.btn_start,
            self.btn_pause,
            self.btn_stop,
            self.btn_run,
            self.btn_cancel_run,
            self.btn_step,
            self.btn_reset_step,
            self.btn_save,
            self.btn_load,
            self.btn_xlsx,
        ])

        # Table
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_context_menu)
        self.table.setAlternatingRowColors(True)

        # Scrollbars + resizing behavior
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)

        # Give a sane default width for some columns
        hdr.resizeSection(0, 50)   # #
        hdr.resizeSection(1, 70)   # channel
        hdr.resizeSection(2, 120)  # action
        hdr.resizeSection(5, 110)  # locator_type
        hdr.resizeSection(10, 70)  # wait_ms

        main.addWidget(self.table)

        # Status bar line
        bottom = QHBoxLayout()
        main.addLayout(bottom)
        self.status = QLabel("Ready.  F10=Step, F8=Reset Step, Esc=Cancel")
        bottom.addWidget(self.status)

        self._update_buttons()
        self._update_step_highlight()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reflow toolbar widgets on window resize
        self.top_bar.relayout(self.width() - 40)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F10:
            self.run_single_step()
            event.accept()
            return
        if event.key() == Qt.Key_F8:
            self.reset_step_pointer()
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.cancel_run()
            event.accept()
            return
        super().keyPressEvent(event)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def _on_project_name_changed(self, text: str) -> None:
        self.state.project.name = text.strip() or "ProgreTomato"
        self.state.project.touch()

    # ----------------------------
    # Target picking (next click)
    # ----------------------------
    def pick_target_window_next_click(self) -> None:
        """
        After clicking this button, the next click anywhere on the screen chooses the target window.
        """
        # Prevent multiple listeners
        self._stop_pick_listener()

        self._set_status("Pick Target: click the app/window you want to automate (next click selects target).")

        my_hwnd = int(self.winId())

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            try:
                wi = get_window_info_from_point(int(x), int(y))

                # If user clicked the workbench itself, ignore and keep listening
                if wi.hwnd == my_hwnd:
                    self._set_status("Clicked Workbench. Click the target application instead...")
                    return

                # Set target
                self.state.set_selected_target(wi.hwnd, wi.title, wi.process_name, wi.pid)
                self.lbl_target.setText(f"Target: {wi.title}  |  {wi.process_name}  |  hwnd={wi.hwnd}")
                self._set_status("Target window captured.")
            finally:
                self._stop_pick_listener()

        self._pick_listener = pynput_mouse.Listener(on_click=on_click)
        self._pick_listener.start()

    def _stop_pick_listener(self) -> None:
        if self._pick_listener:
            try:
                self._pick_listener.stop()
            except Exception:
                pass
            self._pick_listener = None

    # ----------------------------
    # Target-lock filtering during recording
    # ----------------------------
    def _matches_target(self, step: Step) -> bool:
        if not self.chk_target_lock.isChecked():
            return True

        # If no target chosen, don't filter
        if not (self.state.selected_hwnd or self.state.selected_pid or self.state.selected_process_name):
            return True

        # Always keep the recorder lifecycle focus notes
        if step.action == "focus" and (step.notes or "").lower().startswith(("recording started", "recording stopped", "paused", "resumed")):
            return True

        # Prefer PID match
        if self.state.selected_pid and step.pid and step.pid == self.state.selected_pid:
            return True

        # Allow same process if enabled
        if self.chk_same_process.isChecked():
            if self.state.selected_process_name and step.process_name and step.process_name.lower() == self.state.selected_process_name.lower():
                return True

        # Fallback: hwnd match
        if self.state.selected_hwnd and step.hwnd == self.state.selected_hwnd:
            return True

        return False

    # ----------------------------
    # Recording
    # ----------------------------
    def _require_target_for_run(self) -> bool:
        # If target lock is enabled, require a selected target
        if self.chk_target_lock.isChecked():
            if not (self.state.selected_hwnd and self.state.selected_hwnd != int(self.winId())):
                QMessageBox.information(self, "Select target first",
                                        "Pick a target window first (Pick Target), then run.\n"
                                        "This prevents replay from running on top of the Workbench.")
                return False
        return True

    def start_recording(self) -> None:
        if self._is_running_run():
            QMessageBox.warning(self, "Busy", "Automation is currently running. Cancel run first.")
            return
        self.recorder.start()
        self._set_status("Recording...")
        self._update_buttons()

    def toggle_pause(self) -> None:
        if not self.recorder.is_running:
            return
        if self.recorder.is_paused:
            self.recorder.resume()
            self._set_status("Recording...")
        else:
            self.recorder.pause()
            self._set_status("Paused.")
        self._update_buttons()

    def stop_recording(self) -> None:
        self.recorder.stop()
        self._set_status("Stopped.")
        self._update_buttons()

    def _on_step_emitted(self, step: Step) -> None:
        if not self._matches_target(step):
            return
        self.model.add_step(step)
        self._update_step_highlight()

    # ----------------------------
    # Full Run
    # ----------------------------
    def run_automation(self) -> None:
        if self.recorder.is_running:
            QMessageBox.warning(self, "Busy", "Stop recording before running.")
            return
        if self._is_running_run():
            QMessageBox.information(self, "Running", "Already running.")
            return
        if not self.state.project.steps:
            QMessageBox.information(self, "No steps", "No steps to run yet.")
            return
        if not self._require_target_for_run():
            return

        self._stop_run = False
        self._set_status("Starting run... (Esc or Cancel Run to stop)")
        self._update_buttons()

        def worker():
            try:
                runner = Runner(
                    self.state.project,
                    default_hwnd=self.state.selected_hwnd,
                    workbench_hwnd=int(self.winId())
                )
                runner.run(
                    status_cb=lambda s: self._run_signals.status.emit(s),
                    stop_flag=lambda: self._stop_run,
                    step_delay_ms=80,
                )
                self._run_signals.finished.emit("Run finished.")
            except Exception as e:
                self._run_signals.finished.emit(f"Run failed: {e}")

        self._run_thread = threading.Thread(target=worker, daemon=True)
        self._run_thread.start()

    def cancel_run(self) -> None:
        if self._is_running_run():
            self._stop_run = True
            self._set_status("Cancelling run...")

    def _on_run_finished(self, msg: str) -> None:
        self._set_status(msg)
        self._update_buttons()

    def _is_running_run(self) -> bool:
        return self._run_thread is not None and self._run_thread.is_alive()

    def _insert_wait_step(self, row: int, kind: str, **kwargs) -> None:
        """
        Insert a WAIT_UNTIL step BEFORE the given row.
        """
        insert_at = max(0, min(row, len(self.state.project.steps)))

        step = Step(
            channel="win",
            action="wait_until",
            window_title=self.lbl_target.text(),
            process_name=self.state.selected_process_name or "",
            pid=self.state.selected_pid,
            hwnd=self.state.selected_hwnd,
            locator_type="wait",
            locator=kind,
            value="",
            meta={"kind": kind, **kwargs},
            notes=f"WAIT_UNTIL: {kind}",
        )

        self.model.beginInsertRows(QModelIndex(), insert_at, insert_at)
        self.state.project.steps.insert(insert_at, step)
        self.model.endInsertRows()
        self.state.project.touch()

        # keep step pointer sane
        with self._step_lock:
            if self._step_index >= insert_at:
                self._step_index += 1
        self._update_step_highlight()

    # ----------------------------
    # Step Mode
    # ----------------------------
    def reset_step_pointer(self) -> None:
        with self._step_lock:
            self._step_index = 0
        self._update_step_highlight()
        self._set_status("Step pointer reset to 1.")

    def run_single_step(self) -> None:
        if self.recorder.is_running:
            QMessageBox.warning(self, "Busy", "Stop recording before stepping.")
            return
        if self._is_running_run():
            QMessageBox.warning(self, "Busy", "Full run is currently executing. Cancel run first.")
            return
        if not self.state.project.steps:
            return
        if not self._require_target_for_run():
            return


        with self._step_lock:
            idx = self._step_index

        if idx >= len(self.state.project.steps):
            self._set_status("Step mode: already at end. Press F8 to reset.")
            return

        step = self.state.project.steps[idx]

        try:
            runner = Runner(
                self.state.project,
                default_hwnd=self.state.selected_hwnd,
                workbench_hwnd=int(self.winId())
            )
            runner.run_step(step)
            with self._step_lock:
                self._step_index += 1
            self._update_step_highlight()
            self._set_status(f"Step {idx+1}/{len(self.state.project.steps)} executed. (F10 next, F8 reset)")
        except Exception as e:
            self._set_status(f"Step failed at {idx+1}: {e}")

    def _update_step_highlight(self) -> None:
        with self._step_lock:
            idx = self._step_index

        if self.model.rowCount() == 0:
            return

        if idx < 0:
            idx = 0
        if idx >= self.model.rowCount():
            idx = self.model.rowCount() - 1

        self.table.selectRow(idx)
        self.table.scrollTo(self.model.index(idx, 0))

    def _update_buttons(self) -> None:
        recording = self.recorder.is_running
        paused = self.recorder.is_paused
        running_run = self._is_running_run()

        self.btn_start.setEnabled(not recording and not running_run)
        self.btn_pause.setEnabled(recording and not running_run)
        self.btn_pause.setText("Resume" if paused else "Pause")
        self.btn_stop.setEnabled(recording and not running_run)

        self.btn_run.setEnabled((not recording) and (not running_run))
        self.btn_cancel_run.setEnabled(running_run)

        self.btn_step.setEnabled((not recording) and (not running_run))
        self.btn_reset_step.setEnabled((not recording) and (not running_run))

    # ----------------------------
    # File ops
    # ----------------------------
    def save_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Workbench Project (*.json)")
        if not path:
            return
        try:
            save_project_json(self.state.project, path)
            self._set_status(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def load_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Workbench Project (*.json)")
        if not path:
            return
        try:
            proj = load_project_json(path)
            self.state.project = proj
            if not self.state.project.name:
                self.state.project.name = "ProgreTomato"
            self.project_name.setText(self.state.project.name)

            self.model.beginResetModel()
            self.model.project = self.state.project
            self.model.endResetModel()

            with self._step_lock:
                self._step_index = 0
            self._update_step_highlight()

            self._set_status(f"Loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))

    def export_xlsx(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export XLSX", "", "Excel Workbook (*.xlsx)")
        if not path:
            return
        try:
            export_project_xlsx(self.state.project, path)
            self._set_status(f"Exported: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    # ----------------------------
    # Context menu
    # ----------------------------
    def _open_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return

        selected_rows = sorted(set(i.row() for i in self.table.selectionModel().selectedRows()))
        if not selected_rows:
            selected_rows = [idx.row()]

        menu = QMenu(self)

        act_del = menu.addAction("Delete selected step(s)")
        menu.addSeparator()
        act_in = menu.addAction("Mark as Input (set InputRef on selected)")
        act_out = menu.addAction("Mark as Output (set OutputRef on selected)")
        menu.addSeparator()
        act_clear = menu.addAction("Clear InputRef/OutputRef on selected")
        menu.addSeparator()
        act_wait_title = menu.addAction("Insert WAIT: window title contains...")
        act_wait_seconds = menu.addAction("Insert WAIT: seconds...")
        act_wait_clip = menu.addAction("Insert WAIT: clipboard contains...")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if not action:
            return

        if action == act_del:
            self.model.remove_selected(selected_rows)
            with self._step_lock:
                self._step_index = min(self._step_index, max(0, len(self.state.project.steps) - 1))
            self._update_step_highlight()
            return

        if action in (act_in, act_out):
            prompt = "Enter variable name (e.g., username, company_code):"
            name, ok = QInputDialog.getText(self, "Variable Name", prompt)
            if not ok or not name.strip():
                return
            name = name.strip().replace(" ", "_")

            for r in selected_rows:
                step = self.state.project.steps[r]
                if action == act_in:
                    step.input_ref = f"{{{{input:{name}}}}}"
                else:
                    step.output_ref = f"{{{{output:{name}}}}}"
            self.model.dataChanged.emit(
                self.model.index(min(selected_rows), 0),
                self.model.index(max(selected_rows), self.model.columnCount() - 1),
                [Qt.DisplayRole, Qt.EditRole]
            )
            self.state.project.touch()
            return

        if action == act_wait_title:
            text, ok = QInputDialog.getText(self, "Wait Condition", "Window title must contain:")
            if not ok or not text.strip():
                return
            timeout, ok2 = QInputDialog.getInt(self, "Timeout", "Timeout (ms):", 15000, 1000, 600000, 500)
            if not ok2:
                return
            self._insert_wait_step(selected_rows[0], kind="window_title_contains", text=text.strip(), timeout_ms=timeout)
            return

        if action == act_wait_seconds:
            secs, ok = QInputDialog.getDouble(self, "Wait Seconds", "Seconds:", 1.0, 0.0, 600.0, 2)
            if not ok:
                return
            self._insert_wait_step(selected_rows[0], kind="seconds", seconds=secs)
            return

        if action == act_wait_clip:
            text, ok = QInputDialog.getText(self, "Wait Condition", "Clipboard must contain:")
            if not ok or not text.strip():
                return
            timeout, ok2 = QInputDialog.getInt(self, "Timeout", "Timeout (ms):", 10000, 1000, 600000, 500)
            if not ok2:
                return
            self._insert_wait_step(selected_rows[0], kind="clipboard_contains", text=text.strip(), timeout_ms=timeout)
            return

        if action == act_clear:
            for r in selected_rows:
                step = self.state.project.steps[r]
                step.input_ref = ""
                step.output_ref = ""
            self.model.dataChanged.emit(
                self.model.index(min(selected_rows), 0),
                self.model.index(max(selected_rows), self.model.columnCount() - 1),
                [Qt.DisplayRole, Qt.EditRole]
            )
            self.state.project.touch()
            return
