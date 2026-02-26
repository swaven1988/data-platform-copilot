from app.core.execution.backends import BACKENDS


def test_backends_registered():
    assert "local" in BACKENDS
    assert "docker" in BACKENDS
    assert "k8s" in BACKENDS
    assert "airflow" in BACKENDS