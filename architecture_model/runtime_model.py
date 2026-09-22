"""
Runtime architecture data models.

This module contains the data structures used to represent
architecture relationships observed during program execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any


@dataclass
class RuntimeCall:
    """
    Represents a single observed function call during execution.
    """

    caller_module: str
    caller_function: str

    callee_module: str
    callee_function: str

    caller_file: str = ""
    callee_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caller_module": self.caller_module,
            "caller_function": self.caller_function,
            "callee_module": self.callee_module,
            "callee_function": self.callee_function,
            "caller_file": self.caller_file,
            "callee_file": self.callee_file,
        }


@dataclass
class RuntimeRelationship:
    """
    Represents an aggregated runtime relationship between
    two Python modules/components.
    """

    source: str
    target: str

    call_count: int = 0

    functions: Set[str] = field(default_factory=set)

    def add_call(self, function_name: str) -> None:
        self.call_count += 1

        if function_name:
            self.functions.add(function_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "call_count": self.call_count,
            "functions": sorted(self.functions),
        }


@dataclass
class RuntimeArchitecture:
    """
    Complete runtime architecture observed during one execution.
    """

    entry_point: str = ""

    calls: List[RuntimeCall] = field(default_factory=list)

    relationships: Dict[str, RuntimeRelationship] = field(
        default_factory=dict
    )

    modules: Set[str] = field(default_factory=set)

    total_calls: int = 0

    def add_call(self, runtime_call: RuntimeCall) -> None:
        """
        Add a raw runtime call and update aggregated relationships.
        """

        self.calls.append(runtime_call)

        self.total_calls += 1

        if runtime_call.caller_module:
            self.modules.add(runtime_call.caller_module)

        if runtime_call.callee_module:
            self.modules.add(runtime_call.callee_module)

        source = runtime_call.caller_module
        target = runtime_call.callee_module

        # Ignore self-calls at module level.
        if not source or not target or source == target:
            return

        relationship_key = f"{source}->{target}"

        if relationship_key not in self.relationships:
            self.relationships[relationship_key] = RuntimeRelationship(
                source=source,
                target=target,
            )

        self.relationships[relationship_key].add_call(
            runtime_call.callee_function
        )

    def get_relationships(self) -> List[RuntimeRelationship]:
        """
        Return runtime relationships as a list.
        """

        return list(self.relationships.values())

    def get_relationship_count(self) -> int:
        return len(self.relationships)

    def get_module_count(self) -> int:
        return len(self.modules)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the runtime architecture into a serializable dictionary.
        """

        return {
            "entry_point": self.entry_point,
            "total_calls": self.total_calls,
            "module_count": self.get_module_count(),
            "relationship_count": self.get_relationship_count(),
            "modules": sorted(self.modules),
            "calls": [
                call.to_dict()
                for call in self.calls
            ],
            "relationships": [
                relationship.to_dict()
                for relationship in self.get_relationships()
            ],
        }