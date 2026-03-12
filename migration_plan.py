"""
Migrationsplan von VMware zu OpenShift Virtualization.
Phasen, Reihenfolge, Risiken, Zeitschätzung.
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


def build_migration_phases(recommendations: list) -> list:
    """Migrationsphasen aus VM-Empfehlungen ableiten."""
    ready_low = [r.vm_name for r in recommendations if r.status == "ready" and r.effort == "low"]
    ready_medium = [r.vm_name for r in recommendations if r.status == "ready" and r.effort == "medium"]
    ready_high = [r.vm_name for r in recommendations if r.status == "ready" and r.effort == "high"]
    review = [r.vm_name for r in recommendations if r.status == "review"]
    blocked = [r.vm_name for r in recommendations if r.status == "blocked"]

    phases = [
        MigrationPhase(
            name="Phase 1 – Pilot",
            description="VMs mit geringem Risiko und niedrigem Aufwand. Ideal zum Validieren von MTV und OpenShift Virt.",
            vms=ready_low[:10],
            duration_estimate="1–2 Wochen",
            risks=["Minimal – Standard-Cold-Migration"],
            prerequisites=[
                "OpenShift Cluster mit OpenShift Virtualization installiert",
                "Migration Toolkit for Virtualization (MTV) installiert",
                "VMware Source Provider und OpenShift Destination Provider konfiguriert",
                "Netz- und Speicher-Mapping definiert",
            ],
        ),
        MigrationPhase(
            name="Phase 2 – Standard-Workloads",
            description="Weitere VMs mit geringem/mittlerem Aufwand nach erfolgreichem Pilot.",
            vms=ready_low[10:] + ready_medium,
            duration_estimate="2–4 Wochen (abhängig von VM-Anzahl)",
            risks=["Downtime je VM bei Cold-Migration planen"],
            prerequisites=["Pilot-Phase abgeschlossen und validiert", "VDDK-Image für beschleunigte Migration (optional, für vSAN empfohlen)"],
        ),
        MigrationPhase(
            name="Phase 3 – Review-Workloads",
            description="VMs mit besonderen Anforderungen (z. B. viele vCPUs/Speicher). Manuelle Prüfung empfohlen.",
            vms=ready_high + review,
            duration_estimate="Individuell nach Prüfung",
            risks=["Ressourcenlimits auf OpenShift prüfen", "Evtl. VM-Konfiguration anpassen (vCPU/RAM)"],
            prerequisites=["Kapazitätsplanung für große VMs durchgeführt", "Abstimmung mit App-Ownern"],
        ),
        MigrationPhase(
            name="Phase 4 – Manuelle Prüfung / Blocked",
            description="VMs mit fehlenden Daten oder Kompatibilitätsproblemen. Einzelentscheidung nötig.",
            vms=blocked,
            duration_estimate="Nach Klärung",
            risks=["Migration ohne Klärung nicht empfohlen"],
            prerequisites=["RVTools-Daten ergänzen oder VM-Konfiguration in vSphere prüfen", "Entscheidung: Migration, Umbau oder Ausschluss"],
        ),
    ]
    return phases


def generate_plan_markdown(sheets: dict, recommendations: list, stats: dict) -> str:
    """Migrationsplan als Markdown-Report erzeugen."""
    phases = build_migration_phases(recommendations)
    lines = [
        "# Migrationsplan: VMware vSphere → OpenShift Virtualization",
        "",
        f"*Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## 1. Zusammenfassung",
        "",
        f"- **VMs gesamt (für Migration):** {stats['total_vms']}",
        f"- **Bereit (ready):** {stats['ready']}",
        f"- **Prüfung empfohlen (review):** {stats['review']}",
        f"- **Blockiert / Prüfung nötig:** {stats['blocked']}",
        f"- **Empfohlene Cold-Migration:** {stats['cold_recommended']}",
        f"- **Empfohlene Warm-Migration:** {stats['warm_recommended']}",
        f"- **vCPUs gesamt:** {stats['total_vcpus']}",
        f"- **Arbeitsspeicher gesamt:** {stats['total_memory_gib']} GiB",
        f"- **Speicher (provisioned):** {stats['total_storage_gb']} GB",
        f"- **Cluster (Quelle):** {', '.join(stats['clusters']) or '–'}",
        "",
        "## 2. Migrationsphasen",
        "",
    ]
    for p in phases:
        lines.append(f"### {p.name}\n")
        lines.append(p.description + "\n")
        lines.append("**Geschätzte Dauer:** " + p.duration_estimate + "\n")
        if p.vms:
            lines.append("**VMs:**")
            for vm in p.vms[:50]:
                lines.append(f"- {vm}")
            if len(p.vms) > 50:
                lines.append(f"- … und {len(p.vms) - 50} weitere")
        else:
            lines.append("*(Keine VMs in dieser Phase)*")
        lines.append("")
        lines.append("**Voraussetzungen:**")
        for pre in p.prerequisites:
            lines.append(f"- {pre}")
        lines.append("")
        lines.append("**Risiken / Hinweise:**")
        for r in p.risks:
            lines.append(f"- {r}")
        lines.append("")

    lines.extend([
        "## 3. Empfohlene Schritte (MTV)",
        "",
        "1. **OpenShift Virtualization** und **Migration Toolkit for Virtualization (MTV)** installieren.",
        "2. **VMware Source Provider** in MTV konfigurieren (vCenter, Anmeldedaten, ggf. VDDK).",
        "3. **OpenShift Destination Provider** konfigurieren.",
        "4. **Netz-Mapping** und **Speicher-Mapping** anlegen.",
        "5. **Plan** in MTV anlegen und VMs in der empfohlenen Phasenreihenfolge migrieren.",
        "6. Cold-Migration: VM ausschalten → Plan starten → nach Migration auf OpenShift starten.",
        "7. Warm-Migration (wo empfohlen): VM eingeschaltet lassen, MTV führt Warm-Migration durch.",
        "",
        "## 4. Hinweise",
        "",
        "- Speicherangaben aus RVTools sind in **MiB**; MTV nutzt entsprechende Konvertierung.",
        "- **VDDK** ist für vSAN-Quellen erforderlich und beschleunigt Migration generell.",
        "- **NVMe-Disks** (VMware) werden von MTV nicht unterstützt – vor Migration prüfen.",
        "- Dokumentation: [Planning your migration to OpenShift Virtualization (Red Hat)](https://docs.redhat.com/en/documentation/migration_toolkit_for_virtualization/).",
        "",
    ])
    return "\n".join(lines)


def generate_plan_with_risk_markdown(sheets: dict, recommendations: list, stats: dict, global_risks: list, phase_risks: list, risk_summary: dict) -> str:
    """Migration plan markdown including risk analysis section."""
    plan_md = generate_plan_markdown(sheets, recommendations, stats)
    lines = [
        plan_md,
        "",
        "---",
        "",
        "## 5. Risk analysis",
        "",
        f"**Overall risk level:** {risk_summary.get('global_risk_level', 'medium')}",
        f"- High: {risk_summary.get('high_risks', 0)} | Medium: {risk_summary.get('medium_risks', 0)} | Low: {risk_summary.get('low_risks', 0)}",
        "",
        "### Global risks and mitigations",
        "",
    ]
    for r in global_risks:
        lines.append(f"- **[{r.level.upper()}] {r.category}:** {r.description}")
        lines.append(f"  - *Mitigation:* {r.mitigation}")
        lines.append("")
    lines.append("### Per-phase risk")
    for pr in phase_risks:
        lines.append(f"- **{pr.phase_name}**: {pr.level} ({pr.vm_count} VMs)")
        for r in pr.risks:
            lines.append(f"  - {r.description} → {r.mitigation}")
    lines.append("")
    return "\n".join(lines)


def generate_plan_from_file(path: str) -> tuple:
    """RVTools-Datei laden, analysieren und Migrationsplan als Markdown erzeugen."""
    sheets = load_rvtools(path)
    vm_df = get_vm_data(sheets)
    vm_df = filter_vms_for_migration(vm_df)
    recommendations = analyze_all_vms(vm_df)
    stats = summary_stats(vm_df, recommendations)
    plan_md = generate_plan_markdown(sheets, recommendations, stats)
    return sheets, recommendations, stats, plan_md
