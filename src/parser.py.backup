"""
parser.py — AST-based Python Code Parser
"""

import ast
import os


# ================= BASIC HELPERS =================
def read_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def get_docstring(node):
    try:
        return ast.get_docstring(node) or ""
    except Exception:
        return ""


def compute_cyclomatic_complexity(node):
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (
            ast.If, ast.For, ast.While, ast.ExceptHandler,
            ast.With, ast.Assert, ast.comprehension
        )):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def get_called_functions(node):
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
    return list(set(calls))


def get_return_type_hint(node):
    if getattr(node, "returns", None):
        try:
            return ast.unparse(node.returns)
        except Exception:
            return ""
    return ""


def get_arg_types(node):
    args = []
    for arg in node.args.args:
        annotation = ""
        if arg.annotation:
            try:
                annotation = ast.unparse(arg.annotation)
            except Exception:
                pass
        args.append({"name": arg.arg, "type": annotation})
    return args


# ================= MAIN PARSER =================
def parse_file(file_path):

    source_code = read_file(file_path)

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return {
            "file": file_path,
            "error": f"SyntaxError: {e}",
            "functions": [],
            "classes": [],
            "imports": [],
            "global_vars": [],
            "call_graph": {}
        }

    result = {
        "file": file_path,
        "functions": [],
        "classes": [],
        "imports": [],
        "global_vars": [],
        "call_graph": {}
    }

    all_function_names = set()

    # ── Collect all function names ──
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_function_names.add(node.name)

    # ── Extract Data ──
    for node in ast.iter_child_nodes(tree):

        # ================= FUNCTIONS =================
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            calls = get_called_functions(node)
            internal_calls = [c for c in calls if c in all_function_names and c != node.name]

            complexity = compute_cyclomatic_complexity(node)

            func_data = {
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "args": get_arg_types(node),
                "return_type": get_return_type_hint(node),
                "docstring": get_docstring(node),
                "complexity": complexity,
                "complexity_label": "low" if complexity <= 3 else "medium" if complexity <= 7 else "high",
                "calls": internal_calls,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "decorators": [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else []
            }

            result["functions"].append(func_data)
            result["call_graph"][node.name] = internal_calls

        # ================= CLASSES =================
        elif isinstance(node, ast.ClassDef):

            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    pass

            methods = []

            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):

                    calls = get_called_functions(item)
                    internal_calls = [c for c in calls if c in all_function_names and c != item.name]

                    complexity = compute_cyclomatic_complexity(item)

                    method_data = {
                        "name": item.name,
                        "line": item.lineno,
                        "end_line": getattr(item, "end_lineno", item.lineno),  # ✅ FIX
                        "args": get_arg_types(item),
                        "return_type": get_return_type_hint(item),  # ✅ ADDED
                        "docstring": get_docstring(item),
                        "complexity": complexity,
                        "complexity_label": "low" if complexity <= 3 else "medium" if complexity <= 7 else "high",  # ✅ ADDED
                        "is_async": isinstance(item, ast.AsyncFunctionDef),
                        "calls": internal_calls
                    }

                    methods.append(method_data)
                    result["call_graph"][item.name] = internal_calls

            class_data = {
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "bases": bases,
                "docstring": get_docstring(node),
                "methods": methods,
                "decorators": [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else []
            }

            result["classes"].append(class_data)

        # ================= IMPORTS =================
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result["imports"].append(node.module)

        # ================= GLOBAL VARIABLES =================
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result["global_vars"].append({
                        "name": target.id,
                        "line": node.lineno
                    })

    # Remove duplicates
    result["imports"] = list(dict.fromkeys(result["imports"]))

    return result


# ================= FOLDER PARSER =================
def parse_folder(folder_path):
    all_results = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                parsed = parse_file(full_path)
                all_results.append(parsed)
    return all_results


# ================= SUMMARY =================
def get_summary(parsed):

    total_complexity = sum(f.get("complexity", 0) for f in parsed.get("functions", []))
    count = len(parsed.get("functions", []))

    avg_complexity = total_complexity / count if count else 0

    return {
        "file": os.path.basename(parsed.get("file", "")),
        "total_functions": len(parsed.get("functions", [])),
        "total_classes": len(parsed.get("classes", [])),
        "total_imports": len(parsed.get("imports", [])),
        "total_methods": sum(len(c.get("methods", [])) for c in parsed.get("classes", [])),
        "avg_complexity": round(avg_complexity, 2),
        "has_errors": "error" in parsed
    }


# ================= TEST =================
if __name__ == "__main__":
    import json

    sample_code = '''
def add(a, b):
    return a + b
'''

    os.makedirs("../samples", exist_ok=True)
    with open("../samples/sample.py", "w") as f:
        f.write(sample_code)

    result = parse_file("../samples/sample.py")
    print(json.dumps(result, indent=2))
    print("\nSummary:", json.dumps(get_summary(result), indent=2))