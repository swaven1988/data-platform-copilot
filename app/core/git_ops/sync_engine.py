from app.core.git_ops.repo_manager import RepoManager, GitRepositoryError


class SyncDriftError(Exception):
    pass


class SyncEngine:
    def __init__(self, repo_path: str):
        self.repo = RepoManager(repo_path)

    def validate_plan_state(self, baseline_commit: str):
        try:
            self.repo.validate_apply_preconditions(baseline_commit)
        except GitRepositoryError as e:
            raise SyncDriftError(str(e))

    def enforce_idempotent_apply(
        self,
        baseline_commit: str,
        contract_hash: str,
        previous_contract_hash: str | None,
    ):
        self.validate_plan_state(baseline_commit)

        if previous_contract_hash and previous_contract_hash == contract_hash:
            return {"status": "no-op", "reason": "contract hash unchanged"}

        return {"status": "apply-required"}