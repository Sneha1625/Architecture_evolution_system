"""
metrics.py
-----------
Unified Architecture Evidence / Metrics Layer.

This module does NOT invent architectural facts.
It collects and normalizes evidence produced by the
existing architecture-analysis features.

The purpose is to give Architecture Health, RAG,
reports, and future Time Machine analysis one common
evidence structure.
"""

from statistics import mean


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def _inverse_score(value, worst_value):
    """
    Converts a negative metric into a 0-100 health score.

    Example:
        0 violations -> 100
        worst_value violations -> 0
    """
    if worst_value <= 0:
        return 100.0

    return _clamp(
        100.0 - ((float(value) / worst_value) * 100.0)
    )


# ============================================================
# 1. MODULARITY
# ============================================================

def extract_modularity_metrics(modularity_result):
    """
    Extract metrics from community_detector.analyze_modularity().
    """

    if not modularity_result or "error" in modularity_result:
        return {
            "available": False,
            "modularity_score": None,
            "num_communities": 0,
        }

    modularity = modularity_result.get(
        "modularity_score",
        0
    )

    communities = modularity_result.get(
        "num_communities",
        0
    )

    return {
        "available": True,
        "modularity_score": round(
            float(modularity),
            4
        ),
        "num_communities": communities,
    }


# ============================================================
# 2. LOGICAL COUPLING
# ============================================================

def extract_coupling_metrics(coupling_result):
    """
    Extract evidence from mine_logical_coupling().
    """

    if not coupling_result:
        return {
            "available": False,
            "commits_analyzed": 0,
            "files_analyzed": 0,
            "coupled_pairs": 0,
            "strong_pairs": 0,
            "average_coupling": 0.0,
            "maximum_coupling": 0.0,
        }

    couplings = coupling_result.get(
        "couplings",
        []
    )

    scores = [
        float(item.get("coupling_score", 0))
        for item in couplings
    ]

    strong_pairs = [
        score
        for score in scores
        if score >= 70
    ]

    return {
        "available": True,

        "commits_analyzed": coupling_result.get(
            "commits_analyzed",
            0
        ),

        "files_analyzed": coupling_result.get(
            "files_analyzed",
            0
        ),

        "coupled_pairs": len(couplings),

        "strong_pairs": len(strong_pairs),

        "average_coupling": round(
            mean(scores),
            2
        ) if scores else 0.0,

        "maximum_coupling": round(
            max(scores),
            2
        ) if scores else 0.0,
    }


# ============================================================
# 3. CROSS-MODULE ARCHITECTURE
# ============================================================

def extract_cross_module_metrics(cross_module_result):
    """
    Extract architecture-boundary evidence from
    cross_module_analyzer.analyze_project().
    """

    if not cross_module_result:
        return {
            "available": False,
            "files": 0,
            "cross_file_calls": 0,
            "shared_imports": 0,
            "circular_dependencies": 0,
            "dependency_edges": 0,
        }

    matrix = cross_module_result.get(
        "dependency_matrix",
        {}
    )

    dependency_edges = 0

    for source, targets in matrix.items():
        for target, count in targets.items():
            if count > 0:
                dependency_edges += count

    return {
        "available": True,

        "files": len(
            cross_module_result.get(
                "files",
                []
            )
        ),

        "cross_file_calls": len(
            cross_module_result.get(
                "cross_calls",
                []
            )
        ),

        "shared_imports": len(
            cross_module_result.get(
                "shared_imports",
                []
            )
        ),

        "circular_dependencies": len(
            cross_module_result.get(
                "circular_deps",
                []
            )
        ),

        "dependency_edges": dependency_edges,
    }


# ============================================================
# 4. RISK
# ============================================================

def extract_risk_metrics(risk_results):
    """
    Extract evidence from compute_risk_scores().
    """

    if not risk_results:
        return {
            "available": False,
            "files": 0,
            "average_risk": 0.0,
            "maximum_risk": 0.0,
            "high_risk_files": 0,
            "medium_risk_files": 0,
            "low_risk_files": 0,
        }

    scores = [
        float(item.get("risk_score", 0))
        for item in risk_results
    ]

    return {
        "available": True,

        "files": len(risk_results),

        "average_risk": round(
            mean(scores),
            2
        ) if scores else 0.0,

        "maximum_risk": round(
            max(scores),
            2
        ) if scores else 0.0,

        "high_risk_files": sum(
            1
            for item in risk_results
            if item.get("risk_label") == "HIGH"
        ),

        "medium_risk_files": sum(
            1
            for item in risk_results
            if item.get("risk_label") == "MEDIUM"
        ),

        "low_risk_files": sum(
            1
            for item in risk_results
            if item.get("risk_label") == "LOW"
        ),
    }


# ============================================================
# 5. TECHNICAL DEBT
# ============================================================

def extract_debt_metrics(debt_result):
    """
    Extract evidence from calculate_technical_debt().
    """

    if not debt_result:
        return {
            "available": False,
            "functions": 0,
            "classes": 0,
            "estimated_hours": 0.0,
            "estimated_cost": 0.0,
            "complexity_penalty": 0.0,
            "long_function_penalty": 0.0,
        }

    return {
        "available": True,

        "functions": debt_result.get(
            "functions",
            0
        ),

        "classes": debt_result.get(
            "classes",
            0
        ),

        "estimated_hours": debt_result.get(
            "estimated_hours",
            0.0
        ),

        "estimated_cost": debt_result.get(
            "estimated_cost",
            0.0
        ),

        "complexity_penalty": debt_result.get(
            "complexity_penalty",
            0.0
        ),

        "long_function_penalty": debt_result.get(
            "long_function_penalty",
            0.0
        ),
    }


# ============================================================
# 6. CHANGE IMPACT
# ============================================================

def extract_impact_metrics(impact_result):
    """
    Extract evidence from predict_change_impact().
    """

    if not impact_result:
        return {
            "available": False,
            "target_file": None,
            "impacted_files": 0,
            "high_risk_impacted_files": 0,
            "medium_risk_impacted_files": 0,
        }

    impacted = impact_result.get(
        "impacted_files",
        []
    )

    return {
        "available": True,

        "target_file": impact_result.get(
            "target_file"
        ),

        "impacted_files": len(
            impacted
        ),

        "high_risk_impacted_files": sum(
            1
            for item in impacted
            if item.get("risk_label") == "HIGH"
        ),

        "medium_risk_impacted_files": sum(
            1
            for item in impacted
            if item.get("risk_label") == "MEDIUM"
        ),
    }


# ============================================================
# 7. COMPLETE EVIDENCE OBJECT
# ============================================================

def build_architecture_evidence(
    modularity=None,
    coupling=None,
    cross_module=None,
    risk=None,
    debt=None,
    impact=None,
    graph_nodes=0,
    graph_edges=0,
    graph_cycles=0,
):
    """
    Build ONE machine-readable architecture evidence object.

    This object becomes the common input for:

        Architecture Health
        RAG
        Architecture Governance
        Reports
        Time Machine comparisons
    """

    return {
        "graph": {
            "nodes": graph_nodes,
            "edges": graph_edges,
            "cycles": graph_cycles,
        },

        "modularity":
            extract_modularity_metrics(
                modularity
            ),

        "logical_coupling":
            extract_coupling_metrics(
                coupling
            ),

        "cross_module":
            extract_cross_module_metrics(
                cross_module
            ),

        "risk":
            extract_risk_metrics(
                risk
            ),

        "technical_debt":
            extract_debt_metrics(
                debt
            ),

        "change_impact":
            extract_impact_metrics(
                impact
            ),
    }


# ============================================================
# 8. TRANSPARENT HEALTH COMPONENTS
# ============================================================

def calculate_health_components(evidence):
    """
    Produces individual health dimensions.

    These are intentionally transparent and explainable.
    This is NOT the final research weighting model yet.
    """

    components = {}

    # --------------------------------------------------------
    # Cycle safety
    # --------------------------------------------------------

    cycles = evidence["graph"]["cycles"]

    components["cycle_safety"] = _inverse_score(
        cycles,
        worst_value=max(1, evidence["graph"]["nodes"] * 0.05)
    )

    # --------------------------------------------------------
    # Modularity
    # --------------------------------------------------------

    modularity = evidence["modularity"]

    if modularity["available"]:
        # Louvain modularity is normally approximately [-1, 1].
        # In your implementation it is expected in the useful
        # 0-1 range, so convert it to a 0-100 scale.
        components["modularity"] = _clamp(
            modularity["modularity_score"] * 100
        )
    else:
        components["modularity"] = None

    # --------------------------------------------------------
    # Logical coupling
    # --------------------------------------------------------

    coupling = evidence["logical_coupling"]

    if coupling["available"]:
        components["coupling_health"] = _clamp(
            100.0 -
            coupling["average_coupling"]
        )
    else:
        components["coupling_health"] = None

    # --------------------------------------------------------
    # Cross-module architecture
    # --------------------------------------------------------

    cross = evidence["cross_module"]

    if cross["available"]:
        files = max(
            1,
            cross["files"]
        )

        boundary_ratio = (
            cross["cross_file_calls"]
            / files
        )

        components["boundary_health"] = _inverse_score(
            boundary_ratio,
            worst_value=10
        )
    else:
        components["boundary_health"] = None

    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    risk = evidence["risk"]

    if risk["available"]:
        components["risk_health"] = _clamp(
            100.0 -
            risk["average_risk"]
        )
    else:
        components["risk_health"] = None

    # --------------------------------------------------------
    # Debt
    # --------------------------------------------------------

    debt = evidence["technical_debt"]

    if debt["available"]:
        hours = debt["estimated_hours"]

        # Normalize against project size.
        functions = max(
            1,
            debt["functions"]
        )

        hours_per_function = (
            hours / functions
        )

        components["debt_health"] = _inverse_score(
            hours_per_function,
            worst_value=5
        )
    else:
        components["debt_health"] = None

    return components


# ============================================================
# 9. OVERALL HEALTH
# ============================================================

def calculate_overall_health(components):
    """
    Calculates a transparent baseline health score.

    Only available dimensions participate.

    IMPORTANT:
    This is deliberately a baseline. We will later validate
    the final weighting experimentally.
    """

    available = [
        value
        for value in components.values()
        if value is not None
    ]

    if not available:
        return {
            "score": 0.0,
            "status": "NO DATA",
        }

    score = sum(
        available
    ) / len(
        available
    )

    score = round(
        _clamp(score),
        1
    )

    if score >= 80:
        status = "HEALTHY"
    elif score >= 60:
        status = "NEEDS ATTENTION"
    else:
        status = "AT RISK"

    return {
        "score": score,
        "status": status,
    }