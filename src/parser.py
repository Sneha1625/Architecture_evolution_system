"""
Multi-language source parser.

Python continues to use the original AST-based extraction logic.
Other supported languages use tree-sitter-language-pack.

Normalized output keys are kept compatible with the existing application:
file, language, functions, classes, imports, global_vars, call_graph.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any


# Extensions deliberately limited to source-code files (not config or binaries).
EXTENSION_LANGUAGE = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".java": "java",
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
}

IGNORED_DIRECTORIES = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".idea", ".vscode", "build", "dist", "target", "bin", "obj",
    ".next", ".nuxt", "coverage",
}

FUNCTION_TYPES = {
    "function_declaration", "function_definition", "function_item",
    "function_expression", "arrow_function", "generator_function_declaration",
    "method_definition", "method_declaration", "constructor_declaration",
    "local_function_statement", "function", "method", "singleton_method",
}
CLASS_TYPES = {
    "class_declaration", "class_definition", "class_specifier",
    "struct_item", "interface_declaration", "trait_item", "impl_item",
    "enum_declaration", "enum_item", "record_declaration",
}
IMPORT_TYPES = {
    "import_statement", "import_declaration", "import_from_statement",
    "using_directive", "use_declaration", "include_directive",
    "preproc_include", "package_clause", "extern_crate_declaration",
    "require_expression",
}
CALL_TYPES = {
    "call_expression", "call", "method_invocation", "function_call",
    "call_expression",
}
BRANCH_TYPES = {
    "if_statement", "if_expression", "elif_clause", "else_if_clause",
    "for_statement", "for_expression", "while_statement", "while_expression",
    "do_statement", "catch_clause", "except_clause", "conditional_expression",
    "ternary_expression", "case_clause", "switch_case", "match_arm",
    "guard_clause", "unless_modifier", "rescue_clause",
}


def read_file(file_path: str) -> str:
    """Read source using common encodings, without crashing on odd bytes."""
    path = Path(file_path)
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Original Python AST helpers (kept compatible)
# ---------------------------------------------------------------------------

def get_docstring(node: ast.AST) -> str:
    try:
        return ast.get_docstring(node) or ""
    except Exception:
        return ""


def compute_cyclomatic_complexity(node: ast.AST) -> int:
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


def get_called_functions(node: ast.AST) -> list[str]:
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
    return list(dict.fromkeys(calls))


def get_return_type_hint(node: ast.AST) -> str:
    if getattr(node, "returns", None):
        try:
            return ast.unparse(node.returns)
        except Exception:
            return ""
    return ""


def get_arg_types(node: ast.AST) -> list[dict[str, str]]:
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


def _python_function_data(node: ast.AST, all_names: set[str]) -> dict[str, Any]:
    calls = get_called_functions(node)
    name = getattr(node, "name", "")
    internal_calls = [c for c in calls if c in all_names and c != name]
    complexity = compute_cyclomatic_complexity(node)
    decorators = []
    for decorator in getattr(node, "decorator_list", []):
        try:
            decorators.append(ast.unparse(decorator))
        except Exception:
            pass
    return {
        "name": name,
        "line": getattr(node, "lineno", 1),
        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        "args": get_arg_types(node),
        "return_type": get_return_type_hint(node),
        "docstring": get_docstring(node),
        "complexity": complexity,
        "complexity_label": "low" if complexity <= 3 else "medium" if complexity <= 7 else "high",
        "calls": internal_calls,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "decorators": decorators,
    }


def _parse_python(file_path: str, source_code: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source_code, filename=file_path)
    except SyntaxError as exc:
        return {
            "file": file_path, "language": "python",
            "error": f"SyntaxError: {exc}",
            "functions": [], "classes": [], "imports": [],
            "global_vars": [], "call_graph": {},
        }

    result = {
        "file": file_path, "language": "python",
        "functions": [], "classes": [], "imports": [],
        "global_vars": [], "call_graph": {},
    }
    all_names = {
        n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            data = _python_function_data(node, all_names)
            result["functions"].append(data)
            result["call_graph"][node.name] = data["calls"]

        elif isinstance(node, ast.ClassDef):
            methods = []
            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    pass

            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method = _python_function_data(item, all_names)
                    methods.append(method)
                    result["call_graph"][item.name] = method["calls"]

            decorators = []
            for decorator in node.decorator_list:
                try:
                    decorators.append(ast.unparse(decorator))
                except Exception:
                    pass

            result["classes"].append({
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "bases": bases,
                "docstring": get_docstring(node),
                "methods": methods,
                "decorators": decorators,
            })

        elif isinstance(node, ast.Import):
            result["imports"].extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result["imports"].append(node.module)

        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    result["global_vars"].append({
                        "name": target.id,
                        "line": node.lineno,
                    })

    result["imports"] = list(dict.fromkeys(result["imports"]))
    return result


# ---------------------------------------------------------------------------
# Tree-sitter helpers for non-Python languages
# ---------------------------------------------------------------------------

def _node_text(node: Any, source: bytes) -> str:
    if node is None:
        return ""
    try:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _walk(node: Any):
    """Iterate a syntax tree without depending on grammar-specific APIs."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.named_children))


def _field(node: Any, *names: str):
    for name in names:
        try:
            found = node.child_by_field_name(name)
            if found is not None:
                return found
        except Exception:
            pass
    return None


def _first_identifier(node: Any, source: bytes) -> str:
    if node is None:
        return ""
    for child in _walk(node):
        if child.type in {
            "identifier", "type_identifier", "field_identifier",
            "property_identifier", "constant", "name",
        }:
            value = _node_text(child, source)
            if value:
                return value
    return ""


def _function_name(node: Any, source: bytes) -> str:
    name_node = _field(node, "name", "declarator")
    name = _node_text(name_node, source)
    if name and name_node.type not in {"function_declarator"}:
        # Avoid returning a whole typed declarator where a simple name exists.
        return _first_identifier(name_node, source) or name
    if name:
        return _first_identifier(name_node, source) or name
    return _first_identifier(node, source) or f"anonymous_{node.start_point.row + 1}"


def _parameter_items(node: Any, source: bytes) -> list[dict[str, str]]:
    if node is None:
        return []
    output = []
    for child in node.named_children:
        if child.type in {"comment", "line_comment", "block_comment"}:
            continue
        raw = _node_text(child, source)
        if not raw:
            continue
        name = _first_identifier(child, source) or raw
        output.append({"name": name, "type": raw if name != raw else ""})
    return output


def _extract_calls(node: Any, source: bytes) -> list[str]:
    found = []
    for child in _walk(node):
        if child.type not in CALL_TYPES:
            continue
        target = _field(child, "function", "name", "method")
        value = _node_text(target, source) if target is not None else ""
        if not value and child.named_children:
            value = _node_text(child.named_children[0], source)
        # Keep a useful short call name rather than a long expression.
        value = value.split("(")[0].strip()
        value = value.split(".")[-1].strip()
        if value and value not in found:
            found.append(value)
    return found


def _complexity(node: Any) -> int:
    return 1 + sum(1 for child in _walk(node) if child.type in BRANCH_TYPES)


def _parse_tree_sitter(file_path: str, source_code: str, language: str) -> dict[str, Any]:
    result = {
        "file": file_path, "language": language,
        "functions": [], "classes": [], "imports": [],
        "global_vars": [], "call_graph": {},
    }
    try:
        from tree_sitter_language_pack import get_parser
        parser = get_parser(language)
        source = source_code.encode("utf-8")
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as exc:
        result["error"] = f"Parser initialization failed for {language}: {exc}"
        return result

    nodes = list(_walk(root))
    function_nodes = [n for n in nodes if n.type in FUNCTION_TYPES]
    class_nodes = [n for n in nodes if n.type in CLASS_TYPES]
    all_names = {_function_name(n, source) for n in function_nodes}

    # Imports: retain source-level module/import statements.
    for node in nodes:
        if node.type in IMPORT_TYPES or "import" in node.type or node.type in {"use_declaration"}:
            value = _node_text(node, source)
            if value and value not in result["imports"]:
                result["imports"].append(value)

    # Classes and their methods.
    for class_node in class_nodes:
        class_name = _first_identifier(_field(class_node, "name") or class_node, source)
        if not class_name:
            class_name = f"anonymous_class_{class_node.start_point.row + 1}"
        methods = []
        for fn in function_nodes:
            parent = fn.parent
            nearest_class = None
            while parent is not None:
                if parent.type in CLASS_TYPES:
                    nearest_class = parent
                    break
                parent = parent.parent
            if nearest_class is class_node:
                method_name = _function_name(fn, source)
                calls = [c for c in _extract_calls(fn, source) if c in all_names and c != method_name]
                complexity = _complexity(fn)
                args_node = _field(fn, "parameters", "parameter_list", "formal_parameters", "arguments")
                return_node = _field(fn, "return_type", "type")
                methods.append({
                    "name": method_name,
                    "line": fn.start_point.row + 1,
                    "end_line": fn.end_point.row + 1,
                    "args": _parameter_items(args_node, source),
                    "return_type": _node_text(return_node, source),
                    "docstring": "",
                    "complexity": complexity,
                    "complexity_label": "low" if complexity <= 3 else "medium" if complexity <= 7 else "high",
                    "calls": calls,
                    "is_async": "async" in _node_text(fn, source)[:40],
                    "decorators": [],
                })
                result["call_graph"][method_name] = calls

        bases_node = _field(class_node, "superclass", "bases", "interfaces", "extends")
        bases = [_node_text(bases_node, source)] if bases_node is not None else []
        result["classes"].append({
            "name": class_name,
            "line": class_node.start_point.row + 1,
            "end_line": class_node.end_point.row + 1,
            "bases": bases,
            "docstring": "",
            "methods": methods,
            "decorators": [],
        })

    # Top-level functions (exclude functions nested inside classes).
    for fn in function_nodes:
        parent = fn.parent
        inside_class = False
        while parent is not None:
            if parent.type in CLASS_TYPES:
                inside_class = True
                break
            parent = parent.parent
        if inside_class:
            continue

        name = _function_name(fn, source)
        calls = [c for c in _extract_calls(fn, source) if c in all_names and c != name]
        complexity = _complexity(fn)
        args_node = _field(fn, "parameters", "parameter_list", "formal_parameters", "arguments")
        return_node = _field(fn, "return_type", "type")
        data = {
            "name": name,
            "line": fn.start_point.row + 1,
            "end_line": fn.end_point.row + 1,
            "args": _parameter_items(args_node, source),
            "return_type": _node_text(return_node, source),
            "docstring": "",
            "complexity": complexity,
            "complexity_label": "low" if complexity <= 3 else "medium" if complexity <= 7 else "high",
            "calls": calls,
            "is_async": "async" in _node_text(fn, source)[:40],
            "decorators": [],
        }
        result["functions"].append(data)
        result["call_graph"][name] = calls

    # Top-level variable declarations/assignments (best-effort across grammars).
    for node in root.named_children:
        if node.type in {
            "lexical_declaration", "variable_declaration", "const_declaration",
            "static_variable_declaration", "assignment_expression",
            "short_var_declaration", "global_statement",
        }:
            name = _first_identifier(node, source)
            if name:
                result["global_vars"].append({
                    "name": name,
                    "line": node.start_point.row + 1,
                })

    if getattr(root, "has_error", False):
        result["warning"] = "The source contains syntax errors; extracted results may be partial."

    return result


def parse_file(file_path: str) -> dict[str, Any]:
    """Parse one supported source file into the normalized architecture format."""
    try:
        source_code = read_file(file_path)
    except Exception as exc:
        return {
            "file": file_path, "language": EXTENSION_LANGUAGE.get(Path(file_path).suffix.lower(), "unknown"),
            "error": f"File read error: {exc}",
            "functions": [], "classes": [], "imports": [],
            "global_vars": [], "call_graph": {},
        }

    language = EXTENSION_LANGUAGE.get(Path(file_path).suffix.lower())
    if not language:
        return {
            "file": file_path, "language": "unknown",
            "error": f"Unsupported source extension: {Path(file_path).suffix or '(none)'}",
            "functions": [], "classes": [], "imports": [],
            "global_vars": [], "call_graph": {},
        }

    if language == "python":
        return _parse_python(file_path, source_code)
    return _parse_tree_sitter(file_path, source_code, language)


def parse_folder(folder_path: str) -> list[dict[str, Any]]:
    """Parse supported source files recursively, skipping generated/dependency folders."""
    root_path = Path(folder_path)
    if not root_path.is_dir():
        raise ValueError(f"Repository folder does not exist: {folder_path}")

    all_results = []
    for root, dirs, files in os.walk(root_path):
        dirs[:] = sorted(
            d for d in dirs
            if not d.startswith(".") and d not in IGNORED_DIRECTORIES
        )
        for filename in sorted(files):
            extension = Path(filename).suffix.lower()
            if extension not in EXTENSION_LANGUAGE:
                continue
            full_path = os.path.join(root, filename)
            all_results.append(parse_file(full_path))
    return all_results


def get_summary(parsed: dict[str, Any]) -> dict[str, Any]:
    total_complexity = sum(
        f.get("complexity", 0) for f in parsed.get("functions", [])
    )
    count = len(parsed.get("functions", []))
    avg_complexity = total_complexity / count if count else 0

    return {
        "file": os.path.basename(parsed.get("file", "")),
        "language": parsed.get("language", "python"),
        "total_functions": len(parsed.get("functions", [])),
        "total_classes": len(parsed.get("classes", [])),
        "total_imports": len(parsed.get("imports", [])),
        "total_methods": sum(
            len(c.get("methods", [])) for c in parsed.get("classes", [])
        ),
        "avg_complexity": round(avg_complexity, 2),
        "has_errors": "error" in parsed,
    }


if __name__ == "__main__":
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "sample.py"
        sample.write_text(
            '"""Example module."""\n'
            'def add(a: int, b: int) -> int:\n'
            '    if a > 0:\n'
            '        return a + b\n'
            '    return b\n',
            encoding="utf-8",
        )
        parsed = parse_file(str(sample))
        print(json.dumps(parsed, indent=2))
        print("Summary:", json.dumps(get_summary(parsed), indent=2))
