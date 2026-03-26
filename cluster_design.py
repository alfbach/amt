# -*- coding: utf-8 -*-
"""
Cluster design for OpenShift Virtualization: worker count from workload + overcommit.
Savings estimation: density (server reduction) and power consumption vs current hardware.
OpenShift Data Foundation (ODF) hyperconverged storage design.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

# ODF minimum: 3 nodes, 0.5 TiB per device (Red Hat docs)
ODF_MIN_NODES = 3
ODF_MIN_DISK_TIB = 0.5

# Predefined node sizes for optimization
OPTIMIZE_CORES = (16, 32, 64, 96, 128, 192, 256, 512)
OPTIMIZE_MEMORY_GIB = (256, 512, 1024, 2048)

# Cheap hardware limits (max 64 cores, max 2048 GiB)
OPTIMIZE_CHEAP_MAX_CORES = 64
OPTIMIZE_CHEAP_MAX_MEMORY_GIB = 2048


@dataclass
class ODFStorageDesignResult:
    """OpenShift Data Foundation storage design for hyperconverged deployment."""
    enabled: bool
    workload_storage_gb: float
    disks_per_node: int
    disk_size_gb: float
    replication_factor: int
    growth_buffer_pct: float
    num_nodes: int
    raw_total_gb: float
    usable_after_replication_gb: float
    usable_after_buffer_gb: float
    sufficient: bool
    utilization_pct: float
    recommendation: str


@dataclass
class ClusterDesignResult:
    """Result of cluster sizing and savings calculation."""
    workers_needed: int
    total_vcpus: int
    total_memory_gib: float
    worker_cores: int
    worker_memory_gib: float
    cpu_overcommit: float
    memory_overcommit: float
    effective_cores_available: float
    effective_memory_available_gib: float
    cpu_utilization_pct: float
    memory_utilization_pct: float
    current_hosts: int
    current_power_w: float
    new_power_w: float
    density_reduction: int
    density_reduction_pct: float
    power_current_kw: float
    power_new_kw: float
    power_reduction_kw: float
    power_reduction_pct: float


def compute_optimal_node_config(
    total_vcpus: int,
    total_memory_gib: float,
    cpu_overcommit: float = 2.0,
    memory_overcommit: float = 1.0,
    min_workers: int = 3,
    max_utilization_pct: float = 75.0,
    max_cores: Optional[int] = None,
    max_memory_gib: Optional[int] = None,
) -> tuple[int, int, int]:
    """
    Find the (cores, memory_gib) combination that minimizes worker nodes.
    Uses predefined cores (16..512) and memory (256..2048 GiB).
    max_utilization_pct: target max utilization (e.g. 75 = plan for 75% max usage).
    max_cores, max_memory_gib: optional limits for "cheap hardware" mode.
    Returns (optimal_cores, optimal_memory_gib, workers_needed).
    """
    # Scale workload so resulting capacity yields max_utilization_pct usage
    utilization = max_utilization_pct / 100.0
    effective_vcpus = total_vcpus / utilization if utilization > 0 else total_vcpus
    effective_memory_gib = total_memory_gib / utilization if utilization > 0 else total_memory_gib

    cores_pool = [c for c in OPTIMIZE_CORES if max_cores is None or c <= max_cores]
    memory_pool = [m for m in OPTIMIZE_MEMORY_GIB if max_memory_gib is None or m <= max_memory_gib]
    if not cores_pool or not memory_pool:
        cores_pool = cores_pool or [OPTIMIZE_CORES[0]]
        memory_pool = memory_pool or [OPTIMIZE_MEMORY_GIB[0]]

    best_cores = cores_pool[0]
    best_memory = memory_pool[0]
    best_workers = 999999

    for cores in cores_pool:
        for memory_gib in memory_pool:
            design = compute_cluster_design(
                total_vcpus=int(effective_vcpus),
                total_memory_gib=effective_memory_gib,
                worker_cores=cores,
                worker_memory_gib=memory_gib,
                cpu_overcommit=cpu_overcommit,
                memory_overcommit=memory_overcommit,
                current_hosts=0,
                current_power_w=0,
                new_power_w=0,
                min_workers=min_workers,
            )
            if design.workers_needed < best_workers:
                best_workers = design.workers_needed
                best_cores = cores
                best_memory = memory_gib

    return best_cores, best_memory, best_workers


def compute_cluster_design(
    total_vcpus: int,
    total_memory_gib: float,
    worker_cores: int,
    worker_memory_gib: float,
    cpu_overcommit: float = 2.0,
    memory_overcommit: float = 1.0,
    current_hosts: int = 0,
    current_power_w: float = 0.0,
    new_power_w: float = 0.0,
    min_workers: int = 3,
) -> ClusterDesignResult:
    """
    Compute number of worker nodes needed and utilization.
    Overcommit: e.g. cpu_overcommit=2 means 2 vCPUs per physical core allowed.
    """
    if worker_cores <= 0 or worker_memory_gib <= 0:
        effective_cores = 0.0
        effective_memory = 0.0
        workers_needed = 0
        cpu_util = 0.0
        memory_util = 0.0
    else:
        cores_per_worker = worker_cores * cpu_overcommit
        memory_per_worker_gib = worker_memory_gib * memory_overcommit
        workers_by_cpu = max(1, int((total_vcpus / cores_per_worker) + 0.99)) if total_vcpus and cores_per_worker else 1
        workers_by_mem = max(1, int((total_memory_gib / memory_per_worker_gib) + 0.99)) if total_memory_gib and memory_per_worker_gib else 1
        workers_needed = max(min_workers, workers_by_cpu, workers_by_mem)
        effective_cores = workers_needed * cores_per_worker
        effective_memory = workers_needed * memory_per_worker_gib
        cpu_util = (total_vcpus / effective_cores * 100) if effective_cores > 0 else 0.0
        memory_util = (total_memory_gib / effective_memory * 100) if effective_memory > 0 else 0.0

    power_current_kw = (current_hosts * current_power_w) / 1000.0
    power_new_kw = (workers_needed * new_power_w) / 1000.0 if new_power_w > 0 else 0.0
    power_reduction_kw = power_current_kw - power_new_kw
    power_reduction_pct = (power_reduction_kw / power_current_kw * 100) if power_current_kw > 0 else 0.0
    density_reduction = max(0, current_hosts - workers_needed)
    density_reduction_pct = (density_reduction / current_hosts * 100) if current_hosts > 0 else 0.0

    return ClusterDesignResult(
        workers_needed=workers_needed,
        total_vcpus=total_vcpus,
        total_memory_gib=total_memory_gib,
        worker_cores=worker_cores,
        worker_memory_gib=worker_memory_gib,
        cpu_overcommit=cpu_overcommit,
        memory_overcommit=memory_overcommit,
        effective_cores_available=workers_needed * worker_cores * cpu_overcommit if worker_cores > 0 else 0,
        effective_memory_available_gib=workers_needed * worker_memory_gib * memory_overcommit if worker_memory_gib > 0 else 0,
        cpu_utilization_pct=round(cpu_util, 1),
        memory_utilization_pct=round(memory_util, 1),
        current_hosts=current_hosts,
        current_power_w=current_power_w,
        new_power_w=new_power_w,
        density_reduction=density_reduction,
        density_reduction_pct=round(density_reduction_pct, 1),
        power_current_kw=round(power_current_kw, 2),
        power_new_kw=round(power_new_kw, 2),
        power_reduction_kw=round(power_reduction_kw, 2),
        power_reduction_pct=round(power_reduction_pct, 1),
    )


def compute_odf_design(
    workload_storage_gb: float,
    num_worker_nodes: int,
    disks_per_node: int = 2,
    disk_size_gb: float = 1000.0,
    replication_factor: int = 3,
    growth_buffer_pct: float = 25.0,
) -> ODFStorageDesignResult:
    """Design hyperconverged storage with OpenShift Data Foundation (ODF)."""
    if num_worker_nodes < ODF_MIN_NODES or disks_per_node <= 0 or disk_size_gb <= 0:
        return ODFStorageDesignResult(
            enabled=True,
            workload_storage_gb=workload_storage_gb or 0,
            disks_per_node=disks_per_node,
            disk_size_gb=disk_size_gb,
            replication_factor=replication_factor,
            growth_buffer_pct=growth_buffer_pct,
            num_nodes=max(num_worker_nodes, ODF_MIN_NODES),
            raw_total_gb=0,
            usable_after_replication_gb=0,
            usable_after_buffer_gb=0,
            sufficient=False,
            utilization_pct=0,
            recommendation="Configure ODF (disks per node, disk size) and ensure at least 3 worker nodes.",
        )
    workload_storage_gb = workload_storage_gb or 0
    raw_per_node_gb = disks_per_node * disk_size_gb
    raw_total_gb = num_worker_nodes * raw_per_node_gb
    usable_after_replication_gb = raw_total_gb / replication_factor
    buffer_mult = 1.0 - (growth_buffer_pct / 100.0)
    usable_after_buffer_gb = usable_after_replication_gb * buffer_mult
    required_gb = workload_storage_gb
    sufficient = usable_after_buffer_gb >= required_gb
    utilization_pct = (required_gb / usable_after_buffer_gb * 100) if usable_after_buffer_gb > 0 else 0
    if not sufficient:
        rec = f"Increase disks per node, disk size, or add worker nodes. Need ~{required_gb - usable_after_buffer_gb:.0f} GB more usable capacity (after {replication_factor}x replication and {growth_buffer_pct}% growth buffer)."
    else:
        rec = f"ODF design sufficient. Use {replication_factor}-way replication; keep usage under ~{growth_buffer_pct}% of usable for growth."
    return ODFStorageDesignResult(
        enabled=True,
        workload_storage_gb=workload_storage_gb,
        disks_per_node=disks_per_node,
        disk_size_gb=disk_size_gb,
        replication_factor=replication_factor,
        growth_buffer_pct=growth_buffer_pct,
        num_nodes=num_worker_nodes,
        raw_total_gb=round(raw_total_gb, 1),
        usable_after_replication_gb=round(usable_after_replication_gb, 1),
        usable_after_buffer_gb=round(usable_after_buffer_gb, 1),
        sufficient=sufficient,
        utilization_pct=round(utilization_pct, 1),
        recommendation=rec,
    )
