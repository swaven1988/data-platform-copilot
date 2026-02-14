import pytest

from app.plugins.advisors._internal.graph import AdvisorExecutionGraph, AdvisorNode


def test_graph_respects_depends_on():
    g = AdvisorExecutionGraph()

    g.add_node(AdvisorNode(name="A", phase="advise", priority=10, depends_on=[]))
    g.add_node(AdvisorNode(name="B", phase="advise", priority=10, depends_on=["A"]))
    g.add_node(AdvisorNode(name="C", phase="advise", priority=10, depends_on=["B"]))

    order = g.topological_sort()

    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")


def test_graph_dep_order_overrides_priority():
    g = AdvisorExecutionGraph()

    # B has higher priority (smaller number) but depends on A => A must run first
    g.add_node(AdvisorNode(name="A", phase="advise", priority=100, depends_on=[]))
    g.add_node(AdvisorNode(name="B", phase="advise", priority=1, depends_on=["A"]))

    order = g.topological_sort()

    assert order.index("A") < order.index("B")
