# -*- coding: utf-8 -*-
"""
Risk analysis for VMware → OpenShift Virtualization migration.
Categories: technical, downtime, dependency, operational, data.
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
) -> Tuple[List[RiskItem], List[PhaseRiskSummary], dict]:
    """Compute migration risk analysis: global risks, per-phase risks, and summary."""
    global_risks: List[RiskItem] = []
    stats = stats or {}

    blocked = sum(1 for r in recommendations if r.status == "blocked")
    review = sum(1 for r in recommendations if r.status == "review")
    if blocked > 0:
        global_risks.append(RiskItem("technical", "high" if blocked > 5 else "medium",
            f"{blocked} VM(s) blocked or missing data; cannot migrate without resolution.",
            "Fix VM configuration or RVTools data; exclude from scope or resolve before migration."))
    if review > 0:
        global_risks.append(RiskItem("technical", "medium",
            f"{review} VM(s) need review (size, limits, or compatibility).",
            "Validate resource limits and OS compatibility; plan in Phase 3 with owner sign-off."))

    high_effort = sum(1 for r in recommendations if r.effort == "high")
    if high_effort > 0:
        global_risks.append(RiskItem("technical", "medium",
            f"{high_effort} VM(s) with high effort (large disk or resources).",
            "Use cold migration; schedule during maintenance; consider parallel copy and cutover."))

    cold_count = sum(1 for r in recommendations if r.migration_type == "cold")
    if cold_count > 0:
        global_risks.append(RiskItem("downtime", "medium" if cold_count > 10 else "low",
            f"Cold migration required for {cold_count} VM(s) → planned downtime per VM.",
            "Define maintenance windows; communicate to users; test rollback (restore from VMware)."))

    global_risks.append(RiskItem("operational", "medium",
        "Rollback: once migrated, rollback requires re-migration to VMware or restore from backup.",
        "Keep VMware environment available during pilot; document rollback steps; take snapshots."))
    global_risks.append(RiskItem("dependency", "low",
        "VM dependency order (e.g. DB before app) not inferred from RVTools.",
        "Define migration order with application owners; use phases to group by dependency."))
    global_risks.append(RiskItem("data", "medium",
        "Data integrity during copy: network or storage failure can require restart.",
        "Use MTV with VDDK for stable transfer; validate checksums post-migration; test critical VMs first."))

    phase_risks: List[PhaseRiskSummary] = []
    for p in phases:
        risks: List[RiskItem] = []
        if "Pilot" in p.name or "Phase 1" in p.name:
            risks.append(RiskItem("operational", "low", "First wave: unvalidated process and tooling.",
                "Limit to 10 VMs; validate MTV and OpenShift Virt; document runbook."))
        if "Phase 2" in p.name or "Standard" in p.name:
            risks.append(RiskItem("downtime", "medium", "Bulk migration: cumulative downtime and coordination.",
                "Batch by maintenance window; use warm migration where possible."))
        if "Review" in p.name or "Phase 3" in p.name:
            risks.append(RiskItem("technical", "medium", "Large or non-standard VMs; higher failure or rollback risk.",
                "Size OpenShift cluster accordingly; plan extra time and owner approval."))
        if "Blocked" in p.name or "Phase 4" in p.name:
            risks.append(RiskItem("technical", "high", "VMs not ready; migration not recommended without changes.",
                "Resolve blockers or exclude from migration scope."))
        level = _overall_risk_level(risks) if risks else "low"
        phase_risks.append(PhaseRiskSummary(phase_name=p.name, level=level, risks=risks, vm_count=len(p.vms)))

    summary = {
        "global_risk_level": _overall_risk_level(global_risks),
        "high_risks": sum(1 for r in global_risks if r.level == "high"),
        "medium_risks": sum(1 for r in global_risks if r.level == "medium"),
        "low_risks": sum(1 for r in global_risks if r.level == "low"),
    }
    return global_risks, phase_risks, summary
