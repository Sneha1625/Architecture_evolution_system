from architecture_model.recovery import build_components, build_relationships
from architecture_model.architecture_comparison import compare_snapshots
from architecture_model.model import ArchitectureSnapshot


def test_java_classes_in_same_package_remain_separate_and_linked():
    parsed = [
        {
            "file": "src/main/java/com/acme/BankingApp.java",
            "language": "java",
            "imports": ["import com.acme.AccountService;"],
            "classes": [{"name": "BankingApp"}],
            "functions": [],
            "call_graph": {},
        },
        {
            "file": "src/main/java/com/acme/AccountService.java",
            "language": "java",
            "imports": [],
            "classes": [{"name": "AccountService"}],
            "functions": [],
            "call_graph": {},
        },
    ]

    components = build_components(parsed)
    assert len(components) == 2
    relationships = build_relationships(components, parsed)

    assert len(relationships) == 1
    assert relationships[0].source != relationships[0].target
    assert relationships[0].type == "depends_on"


def test_file_addition_is_visible_in_snapshot_comparison():
    old_components = build_components([
        {"file": "src/old.py", "language": "python"}
    ])
    new_components = build_components([
        {"file": "src/old.py", "language": "python"},
        {"file": "src/new.py", "language": "python"},
    ])

    old = ArchitectureSnapshot(
        version="1", commit_hash="old", components=old_components,
        relationships=[], metrics={}, violations=[]
    )
    new = ArchitectureSnapshot(
        version="2", commit_hash="new", components=new_components,
        relationships=[], metrics={}, violations=[]
    )

    comparison = compare_snapshots(old, new)
    assert comparison["summary"]["components_added"] == 1
    assert comparison["summary"]["components_removed"] == 0
