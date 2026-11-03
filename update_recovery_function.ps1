$ErrorActionPreference = "Stop"

$file = ".\architecture_model\recovery.py"

$content = Get-Content $file -Raw

$newFunction = @'
def build_relationships(
    components: List[Component],
    parsed_results: List[Dict[str, Any]]
) -> List[Relationship]:
    """
    Build component-level relationships from Python,
    JavaScript, and TypeScript imports.
    """

    relationships = []
    existing = set()

    file_to_component = {}

    for component in components:
        for file_path in component.files:
            normalized = os.path.normcase(
                os.path.normpath(file_path)
            )
            file_to_component[normalized] = component.id

    def get_component(file_path):
        normalized = os.path.normcase(
            os.path.normpath(file_path)
        )
        return file_to_component.get(normalized)

    # Index project files for resolving relative imports.
    project_files = []

    for result in parsed_results:
        path = (
            result.get("file")
            or result.get("file_path")
            or result.get("path")
            or ""
        )

        if path:
            project_files.append(path)

    def resolve_relative_import(source_file, imported):
        import re

        match = re.search(
            r"""from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]""",
            imported
        )

        if not match:
            return None

        import_path = match.group(1) or match.group(2)

        if not import_path.startswith("."):
            return None

        source_directory = os.path.dirname(source_file)

        target_base = os.path.normpath(
            os.path.join(source_directory, import_path)
        )

        extensions = [
            "",
            ".js", ".jsx", ".mjs", ".cjs",
            ".ts", ".tsx"
        ]

        candidates = []

        for extension in extensions:
            candidates.append(target_base + extension)

        for extension in [".js", ".jsx", ".ts", ".tsx"]:
            candidates.append(
                os.path.join(target_base, "index" + extension)
            )

        normalized_project_files = {
            os.path.normcase(os.path.normpath(path)): path
            for path in project_files
        }

        for candidate in candidates:
            key = os.path.normcase(
                os.path.normpath(candidate)
            )

            if key in normalized_project_files:
                return normalized_project_files[key]

        return None

    # Index Python module names.
    module_to_component = {}

    for component in components:
        for file_path in component.files:
            filename = os.path.basename(file_path)

            if filename.endswith(".py"):
                module_to_component[
                    filename[:-3].lower()
                ] = component.id

    for result in parsed_results:
        source_file = (
            result.get("file")
            or result.get("file_path")
            or result.get("path")
            or ""
        )

        if not source_file:
            continue

        source_component = get_component(source_file)

        if not source_component:
            continue

        language = result.get("language", "").lower()

        for imported in result.get("imports", []):
            if not imported:
                continue

            imported = str(imported).strip()
            target_component = None

            if language in ("javascript", "typescript", "tsx"):
                target_file = resolve_relative_import(
                    source_file,
                    imported
                )

                if target_file:
                    target_component = get_component(target_file)

            elif language == "python":
                module_parts = imported.lower().split(".")

                for length in range(len(module_parts), 0, -1):
                    candidate = ".".join(module_parts[:length])

                    if candidate in module_to_component:
                        target_component = module_to_component[candidate]
                        break

                if not target_component:
                    target_component = module_to_component.get(
                        module_parts[-1]
                    )

            if (
                target_component
                and target_component != source_component
            ):
                key = (
                    source_component,
                    target_component,
                    "depends_on"
                )

                if key not in existing:
                    relationships.append(
                        Relationship(
                            source=source_component,
                            target=target_component,
                            type="depends_on"
                        )
                    )

                    existing.add(key)

                    for component in components:
                        if component.id == source_component:
                            if target_component not in component.dependencies:
                                component.dependencies.append(
                                    target_component
                                )

    return relationships

'@

$pattern = '(?ms)^def build_relationships\(.*?(?=^def recover_architecture\()'

if ($content -notmatch $pattern) {
    throw "Could not find the expected function boundaries. No changes made."
}

$updated = [regex]::Replace(
    $content,
    $pattern,
    [System.Text.RegularExpressions.MatchEvaluator]{
        param($match)
        $newFunction
    },
    1
)

Set-Content -Path $file -Value $updated -Encoding UTF8

Write-Host "build_relationships() updated successfully."