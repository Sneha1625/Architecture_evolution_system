# Runtime evolution language support

Runtime Evolution executes the same relative scenario file in two isolated Git
worktrees, one for each selected commit. The scenario must exist in both
snapshots and must finish within the configured timeout.

## Verified adapter behavior

| Language | Runtime adapter | Evidence shown |
| --- | --- | --- |
| Python | Built-in sys.setprofile tracer | Exact observed Python function-call events |
| JavaScript (.js, .mjs, .cjs) | Node.js V8 CPU profiler | Sampled execution call-tree edges; not exact invocation counts |
| TypeScript (.ts) | Node.js built-in type stripping (Node 22+) | Sampled execution call-tree edges; not exact invocation counts |

TypeScript projects that require JSX, path aliases, decorators, or a custom
build pipeline should provide a compiled JavaScript scenario. JSX/TSX is not
auto-transpiled by this adapter.

## Detected, but not yet call-level instrumented

Java, Go, Rust, C, C++, C#, PHP, and Ruby source files are recognized by
scenario discovery. At present, the runner returns an explicit unsupported
adapter message for these languages rather than pretending static imports are
runtime calls. Their compiler/interpreter being installed is not, by itself,
enough to produce a trustworthy call graph.

## Scenario selection

Automatic discovery prefers files named runtime_scenario.*, main.*, index.js,
cli.py, and similar conventional entry points. For reliable results, add a
small deterministic scenario to the repository and ensure it exists in both
selected commits. Avoid web-server launchers, UI apps, and interactive
processes.

Example JavaScript scenario:

~~~js
const { calculateTotal } = require("./src/cart.js");
console.log(calculateTotal([2, 3]));
~~~

Example Python scenario:

~~~python
from src.cart import calculate_total
print(calculate_total([2, 3]))
~~~

The two selected versions must both contain the scenario and its dependencies.
Use the same Node.js major version and project dependencies when comparing
JavaScript/TypeScript snapshots.

## Interpretation

A Python trace counts observed function-call events. A V8 profile samples
active execution stacks at intervals; the resulting edges indicate sampled
execution paths and must not be interpreted as exact call counts. Short or
mostly idle scenarios may produce few or no V8 samples. A zero-edge profile
does not mean that the application has no static dependencies.

Static architecture graphs and dependency inventories are computed separately
and remain available when runtime tracing cannot be performed.
