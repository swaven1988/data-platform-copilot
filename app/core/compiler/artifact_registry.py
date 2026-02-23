from pathlib import Path
import json


class ArtifactRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, job_name: str, artifact: dict):
        path = self.root / f"{job_name}.json"
        path.write_text(json.dumps(artifact, indent=2))

    def load(self, job_name: str):
        path = self.root / f"{job_name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list(self):
        return [p.stem for p in self.root.glob("*.json")]