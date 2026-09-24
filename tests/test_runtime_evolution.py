from architecture_model.runtime_model import (
    RuntimeArchitecture,
    RuntimeCall,
)

from architecture_model.runtime_evolution import (
    compare_runtime_architectures,
    get_runtime_evolution_summary,
)


# ---------------------------------------------------------
# Simulate Runtime Architecture - Version 1
# ---------------------------------------------------------

runtime_v1 = RuntimeArchitecture(
    entry_point="test_scenario"
)

runtime_v1.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

runtime_v1.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

runtime_v1.add_call(
    RuntimeCall(
        caller_module="features.parser",
        caller_function="parse",
        callee_module="features.validator",
        callee_function="validate",
    )
)


# ---------------------------------------------------------
# Simulate Runtime Architecture - Version 2
# ---------------------------------------------------------

runtime_v2 = RuntimeArchitecture(
    entry_point="test_scenario"
)

runtime_v2.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

runtime_v2.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

runtime_v2.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

# New runtime relationship in V2
runtime_v2.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.database",
        callee_function="save",
    )
)


# ---------------------------------------------------------
# Compare V1 and V2
# ---------------------------------------------------------

comparison = compare_runtime_architectures(
    runtime_v1,
    runtime_v2,
    old_version="V1",
    new_version="V2",
)


print("\n" + "=" * 60)
print("DYNAMIC ARCHITECTURE EVOLUTION TEST")
print("=" * 60)

print("\nV1 Runtime:")
print(comparison["old_runtime"])

print("\nV2 Runtime:")
print(comparison["new_runtime"])

print("\nModules Added:")
print(comparison["module_changes"]["added"])

print("\nModules Removed:")
print(comparison["module_changes"]["removed"])

print("\nRuntime Relationships Added:")
print(comparison["relationship_changes"]["added"])

print("\nRuntime Relationships Removed:")
print(comparison["relationship_changes"]["removed"])

print("\nCall Count Changes:")
print(comparison["relationship_changes"]["call_count_changes"])

print("\nSummary:")
print(comparison["summary"])

print("\nHuman-readable Summary:")
print(
    get_runtime_evolution_summary(
        comparison
    )
)

print("\n" + "=" * 60)
print("TEST COMPLETED")
print("=" * 60)