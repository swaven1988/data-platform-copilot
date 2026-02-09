from pathlib import Path
import yaml
from fastapi import APIRouter, HTTPException

from app.core.spec_schema import CopilotSpec
from app.core.generators.pyspark_gen import render_pyspark_job
from app.core.packaging.packager import make_zip

from app.core.generators.dag_gen import render_airflow_dag
from app.core.generators.spark_conf_gen import render_spark_conf

from app.core.workspace.materialize import materialize_files
from app.core.git_ops.repo_manager import ensure_repo, commit_all, read_baseline, write_baseline



router = APIRouter(prefix="/build", tags=["Build"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../app/api/endpoints -> project root
SPEC_PATH = PROJECT_ROOT / "copilot_spec.yaml"


@router.post("/")
def build_pipeline():
    try:
        if not SPEC_PATH.exists():
            raise FileNotFoundError(f"Spec file not found at: {SPEC_PATH}")

        with SPEC_PATH.open("r", encoding="utf-8") as f:
            spec_dict = yaml.safe_load(f)

        spec = CopilotSpec(**spec_dict)

        generated_files = {}

        if spec.job.language == "pyspark":
            pyspark_code = render_pyspark_job(spec)
            generated_files[f"jobs/pyspark/src/{spec.job.name}.py"] = pyspark_code
        else:
            raise ValueError(f"Unsupported language for MVP: {spec.job.language}")

        dag_code = render_airflow_dag(spec)
        generated_files[f"dags/{spec.job.name}_pipeline.py"] = dag_code

        spark_conf_json = render_spark_conf(spec)
        generated_files["configs/spark_conf_default.json"] = spark_conf_json

        zip_path = make_zip(spec.job.name, generated_files)

        # Materialize into workspace and set baseline (Stage 1)
        workspace_root = PROJECT_ROOT / "workspace"
        workspace_job_dir = workspace_root / spec.job.name

        materialize_files(workspace_job_dir, generated_files)

        # Initialize git + baseline commit (only if baseline not already set)
        ensure_repo(workspace_job_dir)

        baseline = read_baseline(workspace_job_dir)
        if not baseline:
            # 1) Commit generated artifacts
            commit_all(workspace_job_dir, "copilot: baseline")

            # 2) Write baseline.json placeholder and commit it
            write_baseline(workspace_job_dir, "PENDING")
            commit_all(workspace_job_dir, "copilot: baseline snapshot")

            # 3) Now HEAD is the snapshot commit; read it
            baseline_commit = commit_all(workspace_job_dir, "copilot: get snapshot head")

            # NOTE: commit_all above will likely be a no-op and return HEAD. That's fine.

            # 4) Update baseline.json to point to the true snapshot commit and COMMIT it
            write_baseline(workspace_job_dir, baseline_commit)
            baseline_commit = commit_all(workspace_job_dir, "copilot: baseline snapshot (finalize)")

            # 5) Persist final baseline hash in baseline.json (idempotent)
            write_baseline(workspace_job_dir, baseline_commit)
        else:
            baseline_commit = baseline

        return {
            "message": "Generated project artifacts successfully",
            "job_name": spec.job.name,
            "language": spec.job.language,
            "dq_enabled": spec.dq.enabled,
            "spec_path": str(SPEC_PATH),
            "zip_path": zip_path,
            "files": list(generated_files.keys()),
            "workspace_dir": str(workspace_job_dir),
            "baseline_commit": baseline_commit,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
