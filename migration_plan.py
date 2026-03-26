"""
Migrationsplan von VMware zu OpenShift Virtualization.
Phasen, Reihenfolge, Risiken, Zeitschätzung — Texte über i18n-Dict (t).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from analysis import VMRecommendation, analyze_all_vms, summary_stats
from rvtools_parser import filter_vms_for_migration, get_vm_data, load_rvtools


@dataclass
class MigrationPhase:
    name: str
    description: str
    vms: list = field(default_factory=list)
    duration_estimate: str = ""
    risks: list = field(default_factory=list)
    prerequisites: list = field(default_factory=list)


def build_migration_phases(recommendations: list, t: dict) -> list:
    """Migrationsphasen aus VM-Empfehlungen ableiten (lokalisiert)."""
    ready_low = [r.vm_name for r in recommendations if r.status == "ready" and r.effort == "low"]
    ready_medium = [r.vm_name for r in recommendations if r.status == "ready" and r.effort == "medium"]
    ready_high = [r.vm_name for r in recommendations if r.status == "ready" and r.effort == "high"]
    review = [r.vm_name for r in recommendations if r.status == "review"]
    blocked = [r.vm_name for r in recommendations if r.status == "blocked"]

    phases = [
        MigrationPhase(
            name=t["mp_ph1_name"],
            description=t["mp_ph1_desc"],
            vms=ready_low[:10],
            duration_estimate=t["mp_ph1_duration"],
            risks=[t["mp_ph1_risk1"]],
            prerequisites=[
                t["mp_ph1_pre1"],
                t["mp_ph1_pre2"],
                t["mp_ph1_pre3"],
                t["mp_ph1_pre4"],
            ],
        ),
        MigrationPhase(
            name=t["mp_ph2_name"],
            description=t["mp_ph2_desc"],
            vms=ready_low[10:] + ready_medium,
            duration_estimate=t["mp_ph2_duration"],
            risks=[t["mp_ph2_risk1"]],
            prerequisites=[t["mp_ph2_pre1"], t["mp_ph2_pre2"]],
        ),
        MigrationPhase(
            name=t["mp_ph3_name"],
            description=t["mp_ph3_desc"],
            vms=ready_high + review,
            duration_estimate=t["mp_ph3_duration"],
            risks=[t["mp_ph3_risk1"], t["mp_ph3_risk2"]],
            prerequisites=[t["mp_ph3_pre1"], t["mp_ph3_pre2"]],
        ),
        MigrationPhase(
            name=t["mp_ph4_name"],
            description=t["mp_ph4_desc"],
            vms=blocked,
            duration_estimate=t["mp_ph4_duration"],
            risks=[t["mp_ph4_risk1"]],
            prerequisites=[t["mp_ph4_pre1"], t["mp_ph4_pre2"]],
        ),
    ]
    return phases


def _risk_level_tag(level: str, t: dict) -> str:
    return {"high": t["risk_tag_high"], "medium": t["risk_tag_medium"], "low": t["risk_tag_low"]}.get(
        level, level.upper()
    )


def generate_plan_markdown(sheets: dict, recommendations: list, stats: dict, t: dict) -> str:
    """Migrationsplan als Markdown-Report erzeugen (lokalisiert)."""
    phases = build_migration_phases(recommendations, t)
    clusters = ", ".join(stats["clusters"]) or "–"
    lines = [
        t["mp_doc_title"],
        "",
        t["mp_created"].format(date=datetime.now().strftime("%Y-%m-%d %H:%M")),
        "",
        t["mp_sec1_summary"],
        "",
        t["mp_sum_vms"].format(n=stats["total_vms"]),
        t["mp_sum_ready"].format(n=stats["ready"]),
        t["mp_sum_review"].format(n=stats["review"]),
        t["mp_sum_blocked"].format(n=stats["blocked"]),
        t["mp_sum_cold"].format(n=stats["cold_recommended"]),
        t["mp_sum_warm"].format(n=stats["warm_recommended"]),
        t["mp_sum_vcpus"].format(n=stats["total_vcpus"]),
        t["mp_sum_ram"].format(n=stats["total_memory_gib"]),
        t["mp_sum_storage"].format(n=stats["total_storage_gb"]),
        t["mp_sum_clusters"].format(clusters=clusters),
        "",
        t["mp_sec2_phases"],
        "",
    ]
    for p in phases:
        lines.append(f"### {p.name}\n")
        lines.append(p.description + "\n")
        lines.append(t["mp_phase_duration"].format(d=p.duration_estimate) + "\n")
        if p.vms:
            lines.append(t["mp_phase_vms_header"])
            for vm in p.vms[:50]:
                lines.append(f"- {vm}")
            if len(p.vms) > 50:
                lines.append(t["mp_more_vms"].format(n=len(p.vms) - 50))
        else:
            lines.append(t["mp_phase_no_vms"])
        lines.append("")
        lines.append(t["mp_prereq_header"])
        for pre in p.prerequisites:
            lines.append(f"- {pre}")
        lines.append("")
        lines.append(t["mp_risks_header"])
        for r in p.risks:
            lines.append(f"- {r}")
        lines.append("")

    lines.extend(
        [
            t["mp_sec3_mtv"],
            "",
            t["mp_mtv_steps"],
            "",
            t["mp_sec4_notes"],
            "",
            t["mp_notes_body"],
            "",
        ]
    )
    return "\n".join(lines)


def generate_plan_with_risk_markdown(
    sheets: dict,
    recommendations: list,
    stats: dict,
    global_risks: list,
    phase_risks: list,
    risk_summary: dict,
    t: dict,
) -> str:
    """Migration plan markdown including risk analysis section (lokalisiert)."""
    plan_md = generate_plan_markdown(sheets, recommendations, stats, t)
    level = risk_summary.get("global_risk_level", "medium")
    level_disp = t.get(f"risk_level_{level}", level)
    lines = [
        plan_md,
        "",
        "---",
        "",
        t["mp_sec5_risk"],
        "",
        t["mp_risk_overall_line"].format(level=level_disp),
        t["mp_risk_counts_line"].format(
            h=risk_summary.get("high_risks", 0),
            m=risk_summary.get("medium_risks", 0),
            l=risk_summary.get("low_risks", 0),
        ),
        "",
        t["mp_risk_global_header"],
        "",
    ]
    for r in global_risks:
        tag = _risk_level_tag(r.level, t)
        lines.append(
            t["mp_risk_global_item"].format(
                level=tag,
                category=r.category,
                description=r.description,
                mitigation=r.mitigation,
                mit_label=t["mp_mitigation_label"],
            )
        )
        lines.append("")
    lines.append(t["mp_risk_per_phase_header"])
    for pr in phase_risks:
        lvl = t.get(f"risk_level_{pr.level}", pr.level)
        lines.append(
            t["mp_risk_phase_line"].format(
                phase=pr.phase_name,
                level=lvl,
                vm_count=pr.vm_count,
                vms_label=t["vms"],
            )
        )
        for r in pr.risks:
            lines.append(
                t["mp_risk_phase_subitem"].format(
                    description=r.description,
                    mitigation=r.mitigation,
                )
            )
    lines.append("")
    return "\n".join(lines)


def generate_plan_from_file(path: str) -> tuple:
    """RVTools-Datei laden, analysieren und Migrationsplan als Markdown erzeugen."""
    from i18n import get_translations

    sheets = load_rvtools(path)
    vm_df = get_vm_data(sheets)
    vm_df = filter_vms_for_migration(vm_df)
    recommendations = analyze_all_vms(vm_df)
    stats = summary_stats(vm_df, recommendations)
    t = get_translations("en")
    plan_md = generate_plan_markdown(sheets, recommendations, stats, t)
    return sheets, recommendations, stats, plan_md
