# -*- coding: utf-8 -*-
"""
Risk analysis for VMware → OpenShift Virtualization migration.
Categories and texts via i18n dict (t).
"""

from dataclasses import dataclass, field
from typing import Any, List, Tuple

from analysis import VMRecommendation
from migration_plan import MigrationPhase


@dataclass
class RiskItem:
    category: str
    level: str
    description: str
    mitigation: str


@dataclass
class PhaseRiskSummary:
    phase_name: str
    level: str
    risks: List[RiskItem] = field(default_factory=list)
    vm_count: int = 0


def _overall_risk_level(risks: List[RiskItem]) -> str:
    if any(r.level == "high" for r in risks):
        return "high"
    if any(r.level == "medium" for r in risks):
        return "medium"
    return "low"


def compute_risk_analysis(
    recommendations: List[VMRecommendation],
    phases: List[MigrationPhase],
    stats: dict = None,
    t: dict = None,
) -> Tuple[List[RiskItem], List[PhaseRiskSummary], dict]:
    """Compute migration risk analysis: global risks, per-phase risks, and summary."""
    if t is None:
        from i18n import get_translations

        t = get_translations("en")
    global_risks: List[RiskItem] = []
    stats = stats or {}

    blocked = sum(1 for r in recommendations if r.status == "blocked")
    review = sum(1 for r in recommendations if r.status == "review")
    if blocked > 0:
        global_risks.append(
            RiskItem(
                t.get("risk_cat_technical", "technical"),
                "high" if blocked > 5 else "medium",
                t["risk_g_blocked_desc"].format(blocked=blocked),
                t["risk_g_blocked_mit"],
            )
        )
    if review > 0:
        global_risks.append(
            RiskItem(
                t.get("risk_cat_technical", "technical"),
                "medium",
                t["risk_g_review_desc"].format(review=review),
                t["risk_g_review_mit"],
            )
        )

    high_effort = sum(1 for r in recommendations if r.effort == "high")
    if high_effort > 0:
        global_risks.append(
            RiskItem(
                t.get("risk_cat_technical", "technical"),
                "medium",
                t["risk_g_higheffort_desc"].format(n=high_effort),
                t["risk_g_higheffort_mit"],
            )
        )

    cold_count = sum(1 for r in recommendations if r.migration_type == "cold")
    if cold_count > 0:
        global_risks.append(
            RiskItem(
                t.get("risk_cat_downtime", "downtime"),
                "medium" if cold_count > 10 else "low",
                t["risk_g_cold_desc"].format(n=cold_count),
                t["risk_g_cold_mit"],
            )
        )

    global_risks.append(
        RiskItem(
            t.get("risk_cat_operational", "operational"),
            "medium",
            t["risk_g_rollback_desc"],
            t["risk_g_rollback_mit"],
        )
    )
    global_risks.append(
        RiskItem(
            t.get("risk_cat_dependency", "dependency"),
            "low",
            t["risk_g_dependency_desc"],
            t["risk_g_dependency_mit"],
        )
    )
    global_risks.append(
        RiskItem(
            t.get("risk_cat_data", "data"),
            "medium",
            t["risk_g_data_desc"],
            t["risk_g_data_mit"],
        )
    )

    phase_risks: List[PhaseRiskSummary] = []
    for i, p in enumerate(phases):
        risks: List[RiskItem] = []
        if i == 0:
            risks.append(
                RiskItem(
                    t.get("risk_cat_operational", "operational"),
                    "low",
                    t["risk_ph_pilot_desc"],
                    t["risk_ph_pilot_mit"],
                )
            )
        elif i == 1:
            risks.append(
                RiskItem(
                    t.get("risk_cat_downtime", "downtime"),
                    "medium",
                    t["risk_ph_std_desc"],
                    t["risk_ph_std_mit"],
                )
            )
        elif i == 2:
            risks.append(
                RiskItem(
                    t.get("risk_cat_technical", "technical"),
                    "medium",
                    t["risk_ph_review_desc"],
                    t["risk_ph_review_mit"],
                )
            )
        elif i == 3:
            risks.append(
                RiskItem(
                    t.get("risk_cat_technical", "technical"),
                    "high",
                    t["risk_ph_blocked_desc"],
                    t["risk_ph_blocked_mit"],
                )
            )
        level = _overall_risk_level(risks) if risks else "low"
        phase_risks.append(PhaseRiskSummary(phase_name=p.name, level=level, risks=risks, vm_count=len(p.vms)))

    summary = {
        "global_risk_level": _overall_risk_level(global_risks),
        "high_risks": sum(1 for r in global_risks if r.level == "high"),
        "medium_risks": sum(1 for r in global_risks if r.level == "medium"),
        "low_risks": sum(1 for r in global_risks if r.level == "low"),
    }
    return global_risks, phase_risks, summary
