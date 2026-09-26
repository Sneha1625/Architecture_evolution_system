from architecture_model.runtime_model import (
    RuntimeArchitecture,
    RuntimeCall,
)

from database.repository import (
    save_repository,
    save_runtime_execution,
    load_runtime_architecture,
)


# ---------------------------------------------------------
# 1. CREATE TEST REPOSITORY
# ---------------------------------------------------------

repository_id = save_repository(
    name="Runtime Persistence Test",
    source="test",
)

print("Repository ID:", repository_id)


# ---------------------------------------------------------
# 2. CREATE SAMPLE RUNTIME ARCHITECTURE
# ---------------------------------------------------------

runtime = RuntimeArchitecture(
    entry_point="test_scenario"
)

runtime.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

runtime.add_call(
    RuntimeCall(
        caller_module="features.analyzer",
        caller_function="analyze",
        callee_module="features.parser",
        callee_function="parse",
    )
)

runtime.add_call(
    RuntimeCall(
        caller_module="features.parser",
        caller_function="parse",
        callee_module="features.database",
        callee_function="save",
    )
)


# ---------------------------------------------------------
# 3. SAVE RUNTIME ARCHITECTURE
# ---------------------------------------------------------

execution_id = save_runtime_execution(
    repository_id=repository_id,
    runtime_architecture=runtime,
    version="V1",
    commit_hash="test-commit-v1",
    scenario="runtime_persistence_test",
)

print("Execution ID:", execution_id)


# ---------------------------------------------------------
# 4. LOAD RUNTIME ARCHITECTURE
# ---------------------------------------------------------

loaded_runtime = load_runtime_architecture(
    execution_id
)


# ---------------------------------------------------------
# 5. VERIFY RESULTS
# ---------------------------------------------------------

print("\nOriginal Runtime")
print("----------------")
print("Entry Point:", runtime.entry_point)
print("Modules:", sorted(runtime.modules))
print("Total Calls:", runtime.total_calls)
print(
    "Relationships:",
    runtime.get_relationship_count()
)


print("\nLoaded Runtime")
print("--------------")
print("Entry Point:", loaded_runtime.entry_point)
print("Modules:", sorted(loaded_runtime.modules))
print("Total Calls:", loaded_runtime.total_calls)
print(
    "Relationships:",
    loaded_runtime.get_relationship_count()
)


print("\nLoaded Relationships")
print("--------------------")

for relationship in loaded_runtime.get_relationships():

    print(
        relationship.source,
        "->",
        relationship.target,
        "| calls:",
        relationship.call_count,
        "| functions:",
        sorted(relationship.functions),
    )


# ---------------------------------------------------------
# 6. ASSERTIONS
# ---------------------------------------------------------

assert loaded_runtime.entry_point == runtime.entry_point

assert loaded_runtime.total_calls == runtime.total_calls

assert (
    loaded_runtime.get_relationship_count()
    ==
    runtime.get_relationship_count()
)

assert loaded_runtime.modules == runtime.modules


print("\n======================================")
print("RUNTIME PERSISTENCE TEST PASSED")
print("======================================")