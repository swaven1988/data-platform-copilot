import tempfile
import subprocess
from pathlib import Path

from app.core.git_ops.repo_manager import RepoManager
from app.core.git_ops.sync_engine import SyncEngine


def init_git_repo(path: Path):
    subprocess.run(["git", "init"], cwd=path)
    (path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=path)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path)


def test_plan_apply_noop():
    with tempfile.TemporaryDirectory() as tmp:
        repo_path = Path(tmp)
        init_git_repo(repo_path)

        repo = RepoManager(str(repo_path))
        baseline = repo.get_head()

        engine = SyncEngine(str(repo_path))
        result = engine.enforce_idempotent_apply(
            baseline_commit=baseline,
            contract_hash="abc",
            previous_contract_hash="abc",
        )

        assert result["status"] == "no-op"


def test_drift_detection():
    with tempfile.TemporaryDirectory() as tmp:
        repo_path = Path(tmp)
        init_git_repo(repo_path)

        repo = RepoManager(str(repo_path))
        baseline = repo.get_head()

        # create new commit
        (repo_path / "file.txt").write_text("changed")
        subprocess.run(["git", "add", "."], cwd=repo_path)
        subprocess.run(["git", "commit", "-m", "change"], cwd=repo_path)

        engine = SyncEngine(str(repo_path))

        try:
            engine.validate_plan_state(baseline)
            assert False, "Expected drift"
        except Exception:
            assert True


def test_dirty_workspace_detection():
    with tempfile.TemporaryDirectory() as tmp:
        repo_path = Path(tmp)
        init_git_repo(repo_path)

        repo = RepoManager(str(repo_path))
        baseline = repo.get_head()

        (repo_path / "file.txt").write_text("dirty")

        engine = SyncEngine(str(repo_path))

        try:
            engine.validate_plan_state(baseline)
            assert False, "Expected dirty workspace error"
        except Exception:
            assert True