"""
impact_predictor.py — Change Impact / Ripple Effect Predictor
VTU Major Project: AI-Driven Semantic Code Analysis and Automated Software Architecture Modeling System

Answers a question no single existing tool answers directly: "if I change
THIS file, what else is likely to need changes, and how risky is that ripple?"

Combines three signals already computed separately:
  1. Structural dependency graph (src/dependency.py)      — direct callers/callees
  2. Logical coupling (features/coupling_miner.py)         — hidden historical relationships
  3. Risk scores (features/risk_predictor.py)               — complexity + churn + bugfix history
"""

from features.coupling_miner import mine_logical_coupling
from features.risk_predictor import compute_risk_scores

def predict_change_impact(target_file, G, repo_path, parsed_files, max_commits=300):
    """
    Given a file someone is about to change, returns a ranked list of files
    likely to be affected, combining structural neighbors, historical
    coupling partners, and each affected file's own risk score.
    """
    impact_map = {}

    if target_file in G.nodes:
        for neighbor in G.successors(target_file):
            impact_map.setdefault(neighbor, {"reasons": []})
            impact_map[neighbor]["reasons"].append("calls this file")
        for neighbor in G.predecessors(target_file):
            impact_map.setdefault(neighbor, {"reasons": []})
            impact_map[neighbor]["reasons"].append("is called by this file")

    try:
        coupling_result = mine_logical_coupling(repo_path)
        for pair in coupling_result.get("couplings", []):
            a, b = pair["file_a"], pair["file_b"]
            other = None
            if a.endswith(target_file) or target_file.endswith(a):
                other = b
            elif b.endswith(target_file) or target_file.endswith(b):
                other = a
            if other:
                # Skip noise: IDE config, gitignore, compiled bytecode —
                # these aren't real "impacted code" even if git history
                # technically shows them changing alongside the target file.
                if not other.endswith(".py") or "__pycache__" in other:
                    continue
                impact_map.setdefault(other, {"reasons": []})
                impact_map[other]["reasons"].append(
                    f"historically changed together {pair['co_change_count']} times "
                    f"(coupling score {pair['coupling_score']}%)"
                )
    except Exception:
        pass

    try:
        risk_results = compute_risk_scores(parsed_files, repo_path=repo_path, max_commits=max_commits)
        risk_by_file = {r["file"]: r for r in risk_results}
    except Exception:
        risk_by_file = {}

    ranked = []
    for file, info in impact_map.items():
        risk_info = risk_by_file.get(file) or next(
            (v for k, v in risk_by_file.items() if k.endswith(file.split("/")[-1])), None
        )
        ranked.append({
            "file": file,
            "reasons": info["reasons"],
            "risk_score": risk_info["risk_score"] if risk_info else None,
            "risk_label": risk_info["risk_label"] if risk_info else "UNKNOWN"
        })

    def sort_key(item):
        risk = item["risk_score"] if item["risk_score"] is not None else 0
        return (len(item["reasons"]), risk)

    ranked.sort(key=sort_key, reverse=True)

    return {
        "target_file": target_file,
        "total_impacted_files": len(ranked),
        "impacted_files": ranked
    }