from pathlib import Path
from app.core.supply_chain.verification import sha256_file


def test_sha256_deterministic(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = sha256_file(f)
    h2 = sha256_file(f)
    assert h1 == h2