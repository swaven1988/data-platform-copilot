from .local import LocalBackend
from .docker import DockerBackend
from .k8s import K8sBackend
from .airflow import AirflowBackend

BACKENDS = {
    "local": LocalBackend(),
    "docker": DockerBackend(),
    "k8s": K8sBackend(),
    "airflow": AirflowBackend(),
}
