from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.spec_schema import CopilotSpec

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def render_airflow_dag(spec: CopilotSpec) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("airflow/dag.py.j2")

    return template.render(
        job_name=spec.job.name,
        job_description=spec.job.description,
        cron=spec.schedule.cron,
        timezone=spec.schedule.timezone,
        owner=spec.metadata.owner,
        environment=spec.metadata.environment,
    )
