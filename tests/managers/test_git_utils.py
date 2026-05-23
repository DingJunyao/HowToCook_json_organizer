# tests/managers/test_git_utils.py
"""Tests for git_utils module — logic-only tests using temp git repos."""
import subprocess
from pathlib import Path

import pytest

from src.managers.git_utils import (
    GitRepo,
    GitError,
    GitErrorType,
    LocalChanges,
)


def _git(*args, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args), cwd=cwd, check=True, capture_output=True, text=True,
    )


@pytest.fixture
def tmp_git(tmp_path: Path) -> Path:
    """Create a temporary git repo with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", cwd=repo)
    _git("config", "user.email", "test@test.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "hello.json").write_text('{"name": "test"}', encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "initial", cwd=repo)
    return repo


@pytest.fixture
def tmp_clone_env(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create origin + bare remote + clone. Returns (origin, remote, clone)."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", cwd=origin)
    _git("config", "user.email", "test@test.com", cwd=origin)
    _git("config", "user.name", "Test", cwd=origin)
    (origin / "a.json").write_text('{"name": "a"}', encoding="utf-8")
    _git("add", "-A", cwd=origin)
    _git("commit", "-m", "add a", cwd=origin)

    remote = tmp_path / "remote.git"
    # On Windows, git init --bare needs the parent dir to exist
    remote.mkdir()
    _git("init", "--bare", cwd=remote)

    _git("remote", "add", "origin", str(remote), cwd=origin)
    _git("branch", "-M", "main", cwd=origin)
    _git("push", "-u", "origin", "main", cwd=origin)
    # Set remote HEAD to main
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=remote)

    clone = tmp_path / "clone"
    _git("clone", str(remote), str(clone))
    return origin, remote, clone


class TestGitRepoBasics:
    def test_is_git_available(self) -> None:
        assert GitRepo.is_git_available()

    def test_is_valid_repo(self, tmp_git: Path) -> None:
        assert GitRepo(tmp_git).is_valid_repo()
        assert not GitRepo(tmp_git.parent / "nonexistent").is_valid_repo()

    def test_not_a_repo(self, tmp_path: Path) -> None:
        assert not GitRepo(tmp_path).is_valid_repo()

    def test_has_remote(self, tmp_git: Path) -> None:
        assert not GitRepo(tmp_git).has_remote()

    def test_get_branch_info(self, tmp_git: Path) -> None:
        repo = GitRepo(tmp_git)
        # No upstream configured, so get_branch_info should raise
        with pytest.raises(GitError):
            repo.get_branch_info()


class TestLocalChanges:
    def test_clean_repo(self, tmp_git: Path) -> None:
        changes = GitRepo(tmp_git).check_local_changes()
        assert not changes.has_changes

    def test_modified_file(self, tmp_git: Path) -> None:
        (tmp_git / "hello.json").write_text('{"name": "changed"}', encoding="utf-8")
        changes = GitRepo(tmp_git).check_local_changes()
        assert changes.has_changes
        assert "hello.json" in changes.modified_files

    def test_untracked_file(self, tmp_git: Path) -> None:
        (tmp_git / "new.json").write_text('{}', encoding="utf-8")
        changes = GitRepo(tmp_git).check_local_changes()
        assert changes.has_changes
        assert "new.json" in changes.untracked_files


class TestAddCommit:
    def test_add_and_commit(self, tmp_git: Path) -> None:
        repo = GitRepo(tmp_git)
        (tmp_git / "new.json").write_text('{"name": "new"}', encoding="utf-8")
        repo.add_all()
        ok, msg = repo.commit("test commit")
        assert ok
        assert "成功" in msg

    def test_commit_nothing_staged(self, tmp_git: Path) -> None:
        repo = GitRepo(tmp_git)
        ok, msg = repo.commit("nothing")
        assert not ok
        assert "没有" in msg


class TestFormatCommitMessage:
    def test_single_file(self) -> None:
        msg = GitRepo.format_commit_message(["out/a.json"], [])
        assert msg == "chore(recipes): 更新 [a.json]"

    def test_multiple_files(self) -> None:
        msg = GitRepo.format_commit_message(["out/a.json", "out/b.json"], ["out/c.json"])
        assert msg == "chore(recipes): 更新 [a.json, b.json, c.json]"

    def test_many_files_truncated(self) -> None:
        files = [f"out/file{i}.json" for i in range(25)]
        msg = GitRepo.format_commit_message(files, [])
        assert "等 25 个文件" in msg
        assert "file0.json" in msg

    def test_empty(self) -> None:
        msg = GitRepo.format_commit_message([], [])
        assert msg == "chore(recipes): 更新菜谱文件"


class TestPullWithStash:
    def _push_new_commit(self, origin: Path, filename: str, content: str, msg: str) -> None:
        (origin / filename).write_text(content, encoding="utf-8")
        _git("add", "-A", cwd=origin)
        _git("commit", "-m", msg, cwd=origin)
        _git("push", cwd=origin)

    def test_pull_no_local_changes(self, tmp_clone_env: tuple[Path, Path, Path]) -> None:
        origin, remote, clone = tmp_clone_env
        self._push_new_commit(origin, "b.json", '{"name": "b"}', "add b")

        repo = GitRepo(clone)
        success, msg, had_stash, conflicts = repo.pull_with_stash()
        assert success
        assert not had_stash
        assert not conflicts
        assert (clone / "b.json").exists()

    def test_pull_with_local_changes(self, tmp_clone_env: tuple[Path, Path, Path]) -> None:
        origin, remote, clone = tmp_clone_env
        # Modify a TRACKED file (stash only tracks changes to tracked files by default)
        (clone / "a.json").write_text('{"name": "a-modified"}', encoding="utf-8")
        self._push_new_commit(origin, "b.json", '{"name": "b"}', "add b")

        repo = GitRepo(clone)
        success, msg, had_stash, conflicts = repo.pull_with_stash()
        assert success
        assert had_stash
        assert not conflicts
        # Modified content should be preserved
        assert "a-modified" in (clone / "a.json").read_text(encoding="utf-8")
        assert (clone / "b.json").exists()
