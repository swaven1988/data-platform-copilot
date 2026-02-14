from dataclasses import dataclass, field
from typing import Dict, List, Set
from collections import defaultdict, deque


@dataclass
class AdvisorNode:
    name: str
    phase: str
    priority: int
    depends_on: List[str] = field(default_factory=list)


class CircularDependencyError(Exception):
    pass


class AdvisorExecutionGraph:
    def __init__(self):
        self.nodes: Dict[str, AdvisorNode] = {}
        self.edges: Dict[str, List[str]] = defaultdict(list)

    def add_node(self, node: AdvisorNode):
        self.nodes[node.name] = node
        for dep in node.depends_on:
            self.edges[dep].append(node.name)

    def topological_sort(self) -> List[str]:
        in_degree: Dict[str, int] = {name: 0 for name in self.nodes}

        for deps in self.edges.values():
            for node in deps:
                in_degree[node] += 1

        queue = deque(
            sorted(
                [n for n, d in in_degree.items() if d == 0],
                key=lambda n: (
                    self.nodes[n].phase,
                    self.nodes[n].priority,
                    self.nodes[n].name,
                ),
            )
        )

        order: List[str] = []

        while queue:
            current = queue.popleft()
            order.append(current)

            for neighbor in self.edges[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise CircularDependencyError("Circular advisor dependency detected")

        return order
