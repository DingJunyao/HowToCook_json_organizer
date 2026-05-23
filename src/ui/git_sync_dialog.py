# src/ui/git_sync_dialog.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

from src.managers.git_utils import (
    GitRepo,
    GitError,
    GitErrorType,
    RemoteStatus,
    LocalChanges,
)


class SyncWorker(QThread):
    progress = Signal(str)
    remote_status = Signal(object)
    local_changes_signal = Signal(object)
    error = Signal(object)
    finished = Signal(str)

    def __init__(self, repo_dir: Path, action: str):
        super().__init__()
        self.repo_dir = repo_dir
        self.action = action
        self.repo = GitRepo(repo_dir)
        self._changed_files: list[str] = []
        self._untracked_files: list[str] = []

    def set_files_for_commit(self, changed: list[str], untracked: list[str]) -> None:
        self._changed_files = changed
        self._untracked_files = untracked

    def run(self) -> None:
        try:
            if self.action == "check":
                self._do_check()
            elif self.action == "pull":
                self._do_pull()
            elif self.action == "commit_push":
                self._do_commit_push()
        except GitError as e:
            self.error.emit(e)
        except Exception as e:
            self.error.emit(GitError(GitErrorType.UNKNOWN, str(e)))

    def _do_check(self) -> None:
        self.progress.emit("正在检查远程更新...")
        status = self.repo.check_remote_status()
        self.remote_status.emit(status)

        self.progress.emit("正在检查本地更改...")
        changes = self.repo.check_local_changes()
        self.local_changes_signal.emit(changes)

        self.finished.emit("check_done")

    def _do_pull(self) -> None:
        self.progress.emit("正在拉取远程更新...")
        success, msg, _had_stash, conflicts = self.repo.pull_with_stash()
        self.progress.emit(msg)
        if conflicts:
            self.finished.emit("conflict")
        else:
            self.finished.emit("pull_done")

    def _do_commit_push(self) -> None:
        self.progress.emit("正在暂存更改...")
        self.repo.add_all()

        msg = GitRepo.format_commit_message(self._changed_files, self._untracked_files)
        self.progress.emit(f"正在提交: {msg}")
        ok, commit_msg = self.repo.commit(msg)
        if not ok:
            self.progress.emit(f"提交: {commit_msg}")
            self.finished.emit("push_done")
            return

        self.progress.emit("正在推送到远程...")
        ok, push_msg = self.repo.push()
        self.progress.emit(push_msg)
        self.finished.emit("push_done")


class GitSyncDialog(QDialog):
    def __init__(self, repo_dir: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo_dir = repo_dir
        self.repo = GitRepo(repo_dir)
        self._remote_status: RemoteStatus | None = None
        self._local_changes: LocalChanges | None = None

        self.setWindowTitle("仓库同步")
        self.setMinimumSize(560, 420)
        self.setModal(True)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._title_label = QLabel("正在检查远程更新...")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._title_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        self._file_list_label = QLabel("")
        self._file_list_label.setVisible(False)
        layout.addWidget(self._file_list_label)

        self._file_list = QListWidget()
        self._file_list.setVisible(False)
        layout.addWidget(self._file_list)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setStyleSheet("background-color: #f5f5f5;")
        layout.addWidget(self._log)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._pull_btn = QPushButton("拉取更新")
        self._pull_btn.setVisible(False)
        self._pull_btn.clicked.connect(self._on_pull)

        self._push_btn = QPushButton("提交并推送")
        self._push_btn.setVisible(False)
        self._push_btn.clicked.connect(self._on_commit_push)

        self._conflict_resolve_btn = QPushButton("解决冲突后继续")
        self._conflict_resolve_btn.setVisible(False)
        self._conflict_resolve_btn.clicked.connect(self._on_conflict_resolve)

        self._abort_merge_btn = QPushButton("放弃合并")
        self._abort_merge_btn.setVisible(False)
        self._abort_merge_btn.clicked.connect(self._on_abort_merge)

        self._skip_btn = QPushButton("跳过")
        self._skip_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self._pull_btn)
        btn_layout.addWidget(self._push_btn)
        btn_layout.addWidget(self._conflict_resolve_btn)
        btn_layout.addWidget(self._abort_merge_btn)
        btn_layout.addWidget(self._skip_btn)
        layout.addLayout(btn_layout)

    def _log_message(self, msg: str) -> None:
        self._log.append(msg)

    def _show_file_list(self, title: str, files: list[str]) -> None:
        self._file_list_label.setText(title)
        self._file_list_label.setVisible(True)
        self._file_list.clear()
        for f in files:
            self._file_list.addItem(QListWidgetItem(f))
        self._file_list.setVisible(True)

    def _stop_progress(self) -> None:
        self._progress.setRange(0, 100)
        self._progress.setValue(100)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def exec(self) -> int:
        self._run_check()
        return super().exec()

    def _run_check(self) -> None:
        self._worker = SyncWorker(self.repo_dir, "check")
        self._worker.progress.connect(self._log_message)
        self._worker.remote_status.connect(self._on_remote_status)
        self._worker.local_changes_signal.connect(self._on_local_changes)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_check_finished)
        self._worker.start()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_remote_status(self, status: RemoteStatus) -> None:
        self._remote_status = status
        if status.has_updates:
            self._log_message(f"远程有 {status.behind_count} 个新提交")
            self._show_file_list(
                f"远程更新 ({status.behind_count} 个提交)",
                [f"({status.behind_count} commits behind {status.remote_branch})"],
            )

    def _on_local_changes(self, changes: LocalChanges) -> None:
        self._local_changes = changes
        if changes.has_changes:
            self._log_message(
                f"检测到 {len(changes.modified_files)} 个已修改文件, "
                f"{len(changes.untracked_files)} 个未跟踪文件"
            )

    def _on_error(self, error: GitError) -> None:
        self._log_message(f"错误: {error}")
        self._title_label.setText("检查失败")
        self._stop_progress()
        self._skip_btn.setVisible(True)

        if error.error_type == GitErrorType.NETWORK_ERROR:
            self._log_message("网络错误，将跳过同步继续启动。")
        elif error.error_type == GitErrorType.NO_GIT:
            self._log_message("未检测到 git，将跳过同步继续启动。")

    def _on_check_finished(self, step: str) -> None:
        self._stop_progress()

        if self._remote_status and self._remote_status.has_updates:
            self._title_label.setText("检测到远程更新")
            self._pull_btn.setVisible(True)
            self._skip_btn.setText("跳过更新")
        elif self._local_changes and self._local_changes.has_changes:
            self._title_label.setText("检测到本地更改")
            self._show_file_list(
                "未提交的更改",
                self._local_changes.modified_files + self._local_changes.untracked_files,
            )
            self._push_btn.setVisible(True)
            self._skip_btn.setText("跳过")
        else:
            self._title_label.setText("已是最新版本，无本地更改")
            QTimer.singleShot(800, self.accept)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_pull(self) -> None:
        self._pull_btn.setVisible(False)
        self._progress.setRange(0, 0)
        self._log_message("--- 开始拉取 ---")

        self._worker = SyncWorker(self.repo_dir, "pull")
        self._worker.progress.connect(self._log_message)
        self._worker.error.connect(self._on_pull_error)
        self._worker.finished.connect(self._on_pull_finished)
        self._worker.start()

    def _on_pull_error(self, error: GitError) -> None:
        self._log_message(f"拉取错误: {error}")
        self._stop_progress()

        if error.error_type == GitErrorType.CONFLICT:
            self._title_label.setText("合并冲突")
            conflicting = self.repo.get_conflicting_files()
            self._show_file_list("冲突文件", conflicting)
            self._conflict_resolve_btn.setVisible(True)
            self._abort_merge_btn.setVisible(True)
        else:
            self._title_label.setText("拉取失败")
            self._skip_btn.setVisible(True)

    def _on_pull_finished(self, step: str) -> None:
        self._stop_progress()
        self._log_message("拉取完成")

        if self._local_changes and self._local_changes.has_changes:
            self._title_label.setText("拉取完成，检测到本地更改")
            self._show_file_list(
                "未提交的更改",
                self._local_changes.modified_files + self._local_changes.untracked_files,
            )
            self._push_btn.setVisible(True)
        else:
            # Re-check after pull in case new files appeared
            try:
                changes = self.repo.check_local_changes()
                if changes.has_changes:
                    self._local_changes = changes
                    self._title_label.setText("拉取完成，检测到本地更改")
                    self._show_file_list(
                        "未提交的更改",
                        changes.modified_files + changes.untracked_files,
                    )
                    self._push_btn.setVisible(True)
                    return
            except Exception:
                pass

            self._title_label.setText("同步完成")
            QTimer.singleShot(800, self.accept)

    def _on_commit_push(self) -> None:
        self._push_btn.setVisible(False)
        self._progress.setRange(0, 0)
        self._log_message("--- 开始提交并推送 ---")

        changed = self._local_changes.modified_files if self._local_changes else []
        untracked = self._local_changes.untracked_files if self._local_changes else []

        # Re-check for latest changes before committing
        try:
            latest = self.repo.check_local_changes()
            if latest.has_changes:
                changed = latest.modified_files
                untracked = latest.untracked_files
        except Exception:
            pass

        self._worker = SyncWorker(self.repo_dir, "commit_push")
        self._worker.set_files_for_commit(changed, untracked)
        self._worker.progress.connect(self._log_message)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_push_finished)
        self._worker.start()

    def _on_push_finished(self, step: str) -> None:
        self._stop_progress()
        self._title_label.setText("同步完成")
        QTimer.singleShot(800, self.accept)

    def _on_conflict_resolve(self) -> None:
        self._conflict_resolve_btn.setVisible(False)
        self._abort_merge_btn.setVisible(False)
        self._title_label.setText("同步完成 (有冲突需手动处理)")
        QTimer.singleShot(800, self.accept)

    def _on_abort_merge(self) -> None:
        try:
            self.repo.abort_merge()
            self._log_message("已放弃合并")
        except GitError as e:
            self._log_message(f"放弃合并失败: {e}")

        self._conflict_resolve_btn.setVisible(False)
        self._abort_merge_btn.setVisible(False)
        self._file_list.setVisible(False)
        self._file_list_label.setVisible(False)
        self._title_label.setText("已放弃合并")
        self._skip_btn.setVisible(True)

    # ------------------------------------------------------------------
    # Static helper for menu-mode conflict dialog
    # ------------------------------------------------------------------

    @staticmethod
    def show_conflict_dialog(
        repo: GitRepo,
        conflicts: list[str],
        parent: QWidget | None = None,
    ) -> bool:
        """Show a simple conflict dialog. Returns True if user wants to continue."""
        dlg = QDialog(parent)
        dlg.setWindowTitle("合并冲突")
        dlg.setMinimumSize(420, 300)
        dlg.setModal(True)

        layout = QVBoxLayout(dlg)

        label = QLabel("检测到合并冲突，以下文件存在冲突：")
        layout.addWidget(label)

        file_list = QListWidget()
        for f in conflicts:
            file_list.addItem(QListWidgetItem(f))
        layout.addWidget(file_list)

        hint = QLabel("请在外部编辑器解决冲突后点击「继续」，或点击「放弃合并」撤销更改。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        continue_btn = QPushButton("继续")
        continue_btn.clicked.connect(dlg.accept)

        abort_btn = QPushButton("放弃合并")
        def _on_abort() -> None:
            try:
                repo.abort_merge()
            except GitError:
                pass
            dlg.reject()

        abort_btn.clicked.connect(_on_abort)

        btn_row.addWidget(abort_btn)
        btn_row.addWidget(continue_btn)
        layout.addLayout(btn_row)

        result = dlg.exec()
        return result == QDialog.DialogCode.Accepted
