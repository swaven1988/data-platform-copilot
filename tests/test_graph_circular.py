import pytest

from app.plugins.advisors._internal.graph import AdvisorExecutionGraph, AdvisorNode, CircularDependencyError


def test_graph_detects_circular_dependency():
    g = AdvisorExecutionGraph()

    g.add_node(AdvisorNode(name="A", phase="advise", priority=10, depends_on=["C"]))
    g.add_node(AdvisorNode(name="B", phase="advise", priority=10, depends_on=["A"]))
    g.add_node(AdvisorNode(name="C", phase="advise", priority=10, depends_on=["B"]))

    with pytest.raises(CircularDependencyError):
        g.topological_sort()
