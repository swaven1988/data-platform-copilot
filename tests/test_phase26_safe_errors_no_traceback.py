from fastapi.testclient import TestClient
from app.api.main import app


def test_safe_error_middleware_hides_traceback():
    c = TestClient(app)

    r = c.get("/api/v1/does/not/exist")
    assert r.status_code in (401, 404)

    # ensure response doesn't leak tracebacks
    assert "Traceback" not in r.text
    assert "File \"" not in r.text