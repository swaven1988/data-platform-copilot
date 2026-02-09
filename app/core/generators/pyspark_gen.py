from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.spec_schema import CopilotSpec

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def render_pyspark_job(spec: CopilotSpec) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("pyspark/job.py.j2")

    return template.render(
        job_name=spec.job.name,
        job_description=spec.job.description,
        source_identifier=spec.source.identifier,
        target_identifier=spec.target.identifier,
        partition_column=spec.target.partition_column,
        write_mode=spec.target.write_mode,
    )
