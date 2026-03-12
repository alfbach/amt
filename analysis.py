"""
Analyse von VMware-VMs für OpenShift Virtualization und Migration Toolkit for Virtualization (MTV).
Bewertung: Kompatibilität, Risiken, Empfehlungen.
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


# OpenShift Virtualization / KubeVirt typische Limits (konservativ)
MAX_VCPU_PER_VM = 32
MAX_MEMORY_GIB = 256
MIN_MEMORY_MIB = 512
RECOMMENDED_MAX_DISK_GB = 1000
WARM_MIGRATION_MAX_DISK_GB = 500


@dataclass
class VMRecommendation:
    """Empfehlung für eine einzelne VM."""
    vm_name: str
    status: str  # "ready", "review", "blocked"
    migration_type: str  # "cold", "warm", "not_recommended"
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    effort: str = "low"  # low, medium, high
    cluster: str = ""
    cpus: int = 0
    memory_mib: int = 0
    provisioned_gb: float = 0.0
    in_use_gb: float = 0.0


def _safe_int(val: Any) -> int:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _safe_float(val: Any) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _mb_to_gb(mb: float) -> float:
    return round(mb / 1024.0, 2)


def analyze_vm(row: pd.Series) -> VMRecommendation:
    """
    Eine Zeile (eine VM) aus dem RVTools-Export analysieren und
    OpenShift-Virtualization-Empfehlung erzeugen.
    """
    vm_name = str(row.get("vm", row.get("VM", "Unbekannt"))).strip() or "Unbekannt"
    cluster = str(row.get("cluster", "")).strip()
    cpus = _safe_int(row.get("cpus", 0))
    memory_mib = _safe_int(row.get("memory", 0))
    provisioned_mb = _safe_float(row.get("provisioned_mb", 0))
    in_use_mb = _safe_float(row.get("in_use_mb", 0))
    powerstate = str(row.get("powerstate", "")).strip().lower()
    guest_os = str(row.get("guest_os", "")).strip()
    hardware_version = str(row.get("hardware_version", "")).strip()

    rec = VMRecommendation(
        vm_name=vm_name,
        status="ready",
        migration_type="cold",
        cluster=cluster,
        cpus=cpus,
        memory_mib=memory_mib,
        provisioned_gb=_mb_to_gb(provisioned_mb),
        in_use_gb=_mb_to_gb(in_use_mb),
    )

    # CPU-Check
    if cpus > MAX_VCPU_PER_VM:
        rec.issues.append(f"Mehr als {MAX_VCPU_PER_VM} vCPUs – OpenShift Virt Limits prüfen")
        rec.status = "review"
        rec.effort = "high"
    elif cpus == 0:
        rec.issues.append("Keine vCPUs konfiguriert")
        rec.status = "blocked"

    # Memory-Check
    memory_gib = memory_mib / 1024
    if memory_mib > 0 and memory_mib < MIN_MEMORY_MIB:
        rec.recommendations.append("Arbeitsspeicher unter 512 MiB – mind. 512 MiB für Migration empfohlen")
    if memory_gib > MAX_MEMORY_GIB:
        rec.issues.append(f"Arbeitsspeicher > {MAX_MEMORY_GIB} GiB – Cluster-Ressourcen prüfen")
        rec.status = "review"
        rec.effort = "high"

    # Disk-Check (provisioned)
    if rec.provisioned_gb > RECOMMENDED_MAX_DISK_GB:
        rec.issues.append(f"Bereitgestellter Speicher > {RECOMMENDED_MAX_DISK_GB} GB – Migration dauert länger")
        rec.effort = "high" if rec.effort != "high" else rec.effort
    if rec.provisioned_gb > WARM_MIGRATION_MAX_DISK_GB and rec.migration_type == "cold":
        rec.recommendations.append("Warm-Migration bei großer Disk nicht empfohlen – Cold-Migration nutzen")

    # Migrationstyp
    if rec.provisioned_gb > WARM_MIGRATION_MAX_DISK_GB or rec.effort == "high":
        rec.migration_type = "cold"
    else:
        rec.migration_type = "warm" if "on" in powerstate or powerstate == "poweredon" else "cold"

    # OS / VMware Tools (MTV braucht VMware Tools für Warm/Details)
    if not guest_os or guest_os.lower() in ("unknown", "other", ""):
        rec.recommendations.append("Gast-OS in VM prüfen – Kompatibilität mit OpenShift Virt bestätigen")
    if "windows" in guest_os.lower():
        rec.recommendations.append("Windows-VM: Vor Migration Antivirus/Defender temporär prüfen (MTV-Empfehlung)")

    # Hardware-Version (ältere Versionen unkritisch, neuere evtl. Features)
    if hardware_version and "vmx-" in hardware_version.lower():
        rec.recommendations.append(f"Hardware-Version {hardware_version} – wird von KubeVirt/MTV unterstützt")

    if rec.status != "blocked" and not rec.issues:
        rec.recommendations.append("MTV (Migration Toolkit for Virtualization) für Cold/Warm-Migration nutzen")
        rec.recommendations.append("VDDK-Image auf OpenShift für schnellere Migration einplanen (vSAN-Pflicht)")

    return rec


def analyze_all_vms(df: pd.DataFrame) -> list[VMRecommendation]:
    """Alle VMs analysieren und Empfehlungen zurückgeben."""
    if df.empty:
        return []
    return [analyze_vm(row) for _, row in df.iterrows()]


def summary_stats(df: pd.DataFrame, recommendations: list[VMRecommendation]) -> dict[str, Any]:
    """Aggregierte Statistiken und Empfehlungs-Zusammenfassung."""
    total_vms = len(df)
    ready = sum(1 for r in recommendations if r.status == "ready")
    review = sum(1 for r in recommendations if r.status == "review")
    blocked = sum(1 for r in recommendations if r.status == "blocked")
    cold = sum(1 for r in recommendations if r.migration_type == "cold")
    warm = sum(1 for r in recommendations if r.migration_type == "warm")

    total_cpus = df["cpus"].fillna(0).astype("Int64").sum() if "cpus" in df.columns else 0
    total_memory_mib = df["memory"].fillna(0).astype("Int64").sum() if "memory" in df.columns else 0
    total_prov_gb = 0.0
    if "provisioned_mb" in df.columns:
        total_prov_gb = df["provisioned_mb"].fillna(0).astype(float).sum() / 1024.0

    clusters = []
    if "cluster" in df.columns:
        clusters = df["cluster"].dropna().astype(str).unique().tolist()
    clusters = [c for c in clusters if c and str(c).strip() and str(c).lower() != "nan"]

    return {
        "total_vms": total_vms,
        "ready": ready,
        "review": review,
        "blocked": blocked,
        "cold_recommended": cold,
        "warm_recommended": warm,
        "total_vcpus": int(total_cpus),
        "total_memory_gib": round(total_memory_mib / 1024.0, 2),
        "total_storage_gb": round(total_prov_gb, 2),
        "clusters": clusters,
        "recommendations": recommendations,
    }
