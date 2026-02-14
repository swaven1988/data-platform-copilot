from fastapi import APIRouter, Query
from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.graph import AdvisorNode, AdvisorExecutionGraph

router = APIRouter()

def _registry() -> PluginRegistry:
    return PluginRegistry("app/plugins/advisors")

@router.get("/execution/graph")
def get_execution_graph(intent: str = Query(...)):
    reg = _registry()

    # reuse resolver selection logic (same as other routes)
    from app.plugins.advisors._internal.resolver import resolve_advisors
    plugins, _ = resolve_advisors(reg, intent=intent, paths=None, cfg=None)

    graph = AdvisorExecutionGraph()
    for p in plugins:
        pname = getattr(p, "name", p.__class__.__name__)
        graph.add_node(
            AdvisorNode(
                name=pname,
                phase=getattr(p, "phase", "advise"),
                priority=getattr(p, "priority", 100),
                depends_on=getattr(p, "depends_on", []) or [],
            )
        )

    order = graph.topological_sort()

    # edges is a defaultdict(list) -> cast to plain dict for JSON
    return {
        "intent": intent,
        "fingerprint": reg.fingerprint,
        "nodes": list(graph.nodes.keys()),
        "edges": {k: v for k, v in graph.edges.items()},
        "order": order,
    }