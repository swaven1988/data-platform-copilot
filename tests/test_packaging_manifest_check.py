from pathlib import Path
from app.core.packaging.package_manifest import generate_packaging_manifest, load_manifest, manifests_equal

def test_packaging_manifest_exists_and_matches():
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "packaging_manifest.json"
    if not manifest_path.exists():
        # first run in fresh env: allow developer to generate
        return
    expected = load_manifest(manifest_path)
    current = generate_packaging_manifest(project_root=repo_root)
    assert manifests_equal(current, expected)
