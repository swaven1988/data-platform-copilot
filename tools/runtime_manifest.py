from pathlib import Path
from app.core.supply_chain.verification import write_runtime_manifest

if __name__ == "__main__":
    root = Path(".").resolve()
    output = root / "runtime_manifest.json"
    write_runtime_manifest(root, output)
    print("runtime_manifest.json generated")