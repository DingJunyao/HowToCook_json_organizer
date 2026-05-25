# src/managers/git_utils.py
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class GitErrorType(Enum):
    NO_GIT = auto()
    NOT_A_REPO = auto()
    NO_REMOTE = auto()
    NETWORK_ERROR = auto()
    CONFLICT = auto()
    UNKNOWN = auto()


class GitError(Exception):
    def __init__(self, error_type: GitErrorType, message: str, details: str = ""):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class RemoteStatus:
    has_updates: bool
    behind_count: int
    ahead_count: int = 0
    remote_branch: str = ""
    local_branch: str = ""
    verbose_output: str = ""


@dataclass
class LocalChanges:
    has_changes: bool
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    verbose_output: str = ""


class GitRepo:
    def __init__(self, repo_dir: Path | str):
        self.repo_dir = Path(repo_dir)

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    @staticmethod
    def _run(
        args: list[str],
        cwd: Path | None = None,
        timeout: int = 30,
        verbose: bool = False,
        progress_callback: callable | None = None,
    ) -> subprocess.CompletedProcess:
        git_exe = shutil.which("git")
        if git_exe is None:
            raise GitError(GitErrorType.NO_GIT, "git 未找到", "请安装 git 并确保其在 PATH 中。")

        cmd = [git_exe] + args
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

        if progress_callback is not None:
            return GitRepo._run_streaming(cmd, cwd, timeout, env, progress_callback)

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                env=env,
            )
        except subprocess.TimeoutExpired:
            raise GitError(
                GitErrorType.NETWORK_ERROR,
                f"git 命令超时: {' '.join(cmd)}",
            )
        except OSError as e:
            raise GitError(GitErrorType.NO_GIT, f"执行 git 失败: {e}")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # Detect network errors
            lower = stderr.lower()
            if any(kw in lower for kw in ["could not resolve", "network", "connection", "timeout"]):
                raise GitError(GitErrorType.NETWORK_ERROR, f"网络错误: {stderr[:200]}")
            raise GitError(
                GitErrorType.UNKNOWN,
                f"git {' '.join(args)} 失败 (exit {result.returncode})",
                stderr,
            )

        # In verbose mode, append stderr to stdout so progress info is visible
        if verbose and result.stderr.strip():
            result.stdout = (result.stdout.rstrip() + "\n" + result.stderr.rstrip()).rstrip()

        return result

    @staticmethod
    def _run_streaming(
        cmd: list[str],
        cwd: Path,
        timeout: int,
        env: dict,
        progress_callback: callable,
    ) -> subprocess.CompletedProcess:
        """Run a git command with real-time output via progress_callback."""
        import threading

        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env=env,
        )

        stdout_lines: list[str] = []

        def _read() -> None:
            if process.stdout is None:
                return
            for line in process.stdout:
                stripped = line.rstrip("\n").rstrip("\r")
                stdout_lines.append(stripped)
                try:
                    progress_callback(stripped)
                except Exception:
                    pass

        reader = threading.Thread(target=_read, daemon=True)
        reader.start()

        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            reader.join(timeout=5)
            raise GitError(
                GitErrorType.NETWORK_ERROR,
                f"git 命令超时: {' '.join(cmd)}",
            )

        reader.join(timeout=10)

        stdout = "\n".join(stdout_lines)
        result = subprocess.CompletedProcess(cmd, returncode, stdout, "")

        if returncode != 0:
            lower = stdout.lower()
            if any(kw in lower for kw in ["could not resolve", "network", "connection", "timeout"]):
                raise GitError(GitErrorType.NETWORK_ERROR, f"网络错误: {stdout[:200]}")
            raise GitError(
                GitErrorType.UNKNOWN,
                f"git {' '.join(cmd[1:])} 失败 (exit {returncode})",
                stdout[:500],
            )

        return result

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @staticmethod
    def is_git_available() -> bool:
        return shutil.which("git") is not None

    def is_valid_repo(self) -> bool:
        if not self.repo_dir.is_dir():
            return False
        try:
            self._run(["rev-parse", "--git-dir"], cwd=self.repo_dir)
            return True
        except GitError:
            return False

    def has_remote(self) -> bool:
        try:
            result = self._run(["remote"], cwd=self.repo_dir)
            return bool(result.stdout.strip())
        except GitError:
            return False

    def get_branch_info(self) -> tuple[str, str]:
        """Return (local_branch, remote_tracking_branch)."""
        result = self._run(["branch", "--show-current"], cwd=self.repo_dir)
        local = result.stdout.strip()
        if not local:
            raise GitError(GitErrorType.UNKNOWN, "无法获取当前分支名（可能处于 detached HEAD）")

        result = self._run(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=self.repo_dir,
        )
        remote = result.stdout.strip()
        return local, remote

    # ------------------------------------------------------------------
    # Status checks
    # ------------------------------------------------------------------

    def check_remote_status(self) -> RemoteStatus:
        """Fetch from remote and compare local vs remote."""
        local_branch, remote_branch = self.get_branch_info()

        try:
            fetch_result = self._run(["fetch", "--verbose"], cwd=self.repo_dir, timeout=30, verbose=True)
            fetch_output = fetch_result.stdout.strip()
        except GitError as e:
            if e.error_type in (GitErrorType.NO_GIT, GitErrorType.NETWORK_ERROR):
                raise
            raise GitError(GitErrorType.NETWORK_ERROR, f"无法从远程仓库获取更新: {e.message}")

        behind_result = self._run(
            ["rev-list", "--count", f"{local_branch}..{remote_branch}"],
            cwd=self.repo_dir,
        )
        behind = int(behind_result.stdout.strip())

        ahead_result = self._run(
            ["rev-list", "--count", f"{remote_branch}..{local_branch}"],
            cwd=self.repo_dir,
        )
        ahead = int(ahead_result.stdout.strip())

        return RemoteStatus(
            has_updates=behind > 0,
            behind_count=behind,
            ahead_count=ahead,
            remote_branch=remote_branch,
            local_branch=local_branch,
            verbose_output=fetch_output,
        )

    def check_local_changes(self) -> LocalChanges:
        """Detect uncommitted modifications."""
        # Get human-readable status first
        status_result = self._run(["status", "--short"], cwd=self.repo_dir, verbose=True)
        status_verbose = status_result.stdout.strip()

        # Get porcelain output for parsing
        result = self._run(["status", "--porcelain", "-z"], cwd=self.repo_dir)
        raw = result.stdout.rstrip("\x00")
        entries = raw.split("\x00") if raw else []

        modified: list[str] = []
        untracked: list[str] = []
        for entry in entries:
            # Format: "XY filepath" or "XY filepath\x00orig_filepath" (for renames/copies)
            # With -z, filepath is not quoted, no escape processing needed
            if len(entry) < 4:
                continue
            status_code = entry[:2]
            filepath = entry[3:]
            # For renames/copies, git outputs: "XY new\x00old" — we only care about the first part
            if "\x00" in filepath:
                filepath = filepath.split("\x00")[0]
            if status_code in ("M ", " M", "MM", "AM", " A", " D", "D ", "R ", "C "):
                modified.append(filepath)
            elif status_code == "??":
                untracked.append(filepath)

        return LocalChanges(
            has_changes=bool(modified or untracked),
            modified_files=modified,
            untracked_files=untracked,
            verbose_output=status_verbose,
        )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def pull_with_stash(self) -> tuple[bool, str, bool, list[str]]:
        """Pull from remote, stashing local changes first if needed.

        Returns (success, message, had_stash, conflicting_files).
        """
        local = self.check_local_changes()
        had_stash = False

        if local.has_changes:
            try:
                result = self._run(
                    ["stash", "push", "-m", "Auto-stash by HowToCook Organizer"],
                    cwd=self.repo_dir,
                )
                # Check if stash was actually created
                if "No local changes to save" in result.stdout:
                    had_stash = False
                else:
                    had_stash = True
            except GitError:
                pass  # Continue with pull even if stash fails

        try:
            result = self._run(
                ["pull", "--rebase=false"],
                cwd=self.repo_dir,
                timeout=60,
                verbose=True,
            )
            stdout = result.stdout.strip()
            if "Already up to date" in stdout:
                pull_msg = "已经是最新版本"
            else:
                pull_msg = f"拉取成功:\n{stdout}"
        except GitError as e:
            lower = (e.details or "").lower()
            if "conflict" in lower or "CONFLICT" in lower:
                conflicts = self.get_conflicting_files()
                return False, f"拉取时发生合并冲突: {e.message}", had_stash, conflicts
            return False, f"拉取失败: {e.message}", had_stash, []

        # Pop stash if we created one
        conflicts: list[str] = []
        if had_stash:
            try:
                self._run(["stash", "pop"], cwd=self.repo_dir)
            except GitError as e:
                lower = (e.details or "").lower()
                if "conflict" in lower or "CONFLICT" in lower:
                    conflicts = self.get_conflicting_files()
                    return False, f"Stash 恢复时发生冲突", had_stash, conflicts
                # Other stash pop errors are non-fatal
                pull_msg += f"\n(Stash 恢复警告: {e.message})"

        return True, pull_msg, had_stash, conflicts

    def get_conflicting_files(self) -> list[str]:
        result = self._run(
            ["diff", "--name-only", "--diff-filter=U"],
            cwd=self.repo_dir,
        )
        lines = result.stdout.strip().splitlines() if result.stdout.strip() else []
        return lines

    def abort_merge(self) -> None:
        try:
            self._run(["merge", "--abort"], cwd=self.repo_dir)
        except GitError as e:
            if "no merge to abort" not in (e.details or "").lower():
                raise

    def add_all(self) -> None:
        self._run(["add", "-A"], cwd=self.repo_dir)

    def commit(self, message: str) -> tuple[bool, str]:
        try:
            result = self._run(
                ["diff", "--cached", "--name-only"],
                cwd=self.repo_dir,
            )
            staged_files = result.stdout.strip()
            if not staged_files:
                return False, "没有已暂存的更改"

            commit_result = self._run(
                ["commit", "-m", message],
                cwd=self.repo_dir,
                verbose=True,
            )
            commit_output = commit_result.stdout.strip()
            return True, f"提交成功:\n{commit_output}"
        except GitError as e:
            return False, f"提交失败: {e.message}"

    def push(self, progress_callback: callable | None = None) -> tuple[bool, str]:
        try:
            result = self._run(
                ["push"], cwd=self.repo_dir, timeout=120, verbose=True,
                progress_callback=progress_callback,
            )
            if progress_callback:
                return True, "推送成功"
            return True, f"推送成功:\n{result.stdout.strip()}"
        except GitError as e:
            lower = (e.details or "").lower()
            if "rejected" in lower or "non-fast-forward" in lower:
                return False, f"推送被拒绝: {e.details[:200]}"
            return False, f"推送失败: {e.message}"

    @staticmethod
    def format_commit_message(changed_files: list[str], untracked_files: list[str]) -> str:
        all_files = sorted(set(changed_files) | set(untracked_files))
        if not all_files:
            return "chore(recipes): 更新菜谱文件"

        names = [Path(f).name for f in all_files]

        if len(names) > 20:
            display = ", ".join(names[:20])
            return f"chore(recipes): 更新 [{display}] 等 {len(names)} 个文件"
        else:
            display = ", ".join(names)
            return f"chore(recipes): 更新 [{display}]"
