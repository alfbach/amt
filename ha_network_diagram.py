# -*- coding: utf-8 -*-
"""
High Availability design and network diagram for OpenShift cluster.
Produces Graphviz DOT and recommended network settings.
"""

from typing import List, Tuple


def get_ha_recommendations(
    workers_needed: int,
    ha_enabled: bool,
    ha_min_workers: int,
    odf_enabled: bool,
) -> List[str]:
    """Return list of HA design recommendations."""
    recs = []
    if not ha_enabled:
        recs.append("HA is disabled. Enable for production to tolerate node failures.")
        return recs
    min_nodes = max(ha_min_workers, 3)
    if workers_needed < min_nodes and workers_needed > 0:
        recs.append(f"For HA, use at least {min_nodes} worker nodes (current design: {workers_needed}).")
    elif workers_needed >= min_nodes:
        recs.append(f"HA design: {workers_needed} worker nodes (≥ {min_nodes} for HA).")
    recs.append("Spread worker nodes across availability zones or racks where possible.")
    recs.append("OpenShift control plane: 3 nodes (schedulable or dedicated) for HA.")
    if odf_enabled:
        recs.append("ODF requires minimum 3 nodes; replication across nodes for storage HA.")
    recs.append("Use multiple NICs with bonding (active-backup or balance-slb) for network HA.")
    return recs


def get_network_settings() -> List[Tuple[str, str]]:
    """Return recommended network settings as (label, value) for OpenShift + Virt + ODF."""
    return [
        ("NIC MTU", "9000 (jumbo) for storage/VM traffic, or 1500 (standard)"),
        ("Cluster network MTU", "50–100 bytes below NIC MTU (e.g. 8950 or 1450)"),
        ("Bonding", "active-backup (fault tolerance) or balance-slb (load balance)"),
        ("VLANs / networks", "API, Ingress, default pod, ODF/Storage, VM/Migration"),
        ("Migration network (MTV)", "Dedicated VLAN or segment; MTU must match OpenShift"),
    ]


def build_topology_dot(
    num_workers: int,
    worker_cores: int,
    worker_memory_gib: int,
) -> str:
    """Build Graphviz DOT for cluster topology and recommended network."""
    n_show = min(max(1, num_workers), 6)
    lines = [
        "digraph G {",
        "  rankdir=TB;",
        "  node [shape=box, style=rounded, fontname=Helvetica];",
        "  compound=true;",
        "",
        "  subgraph cluster_network {",
        '    label="Recommended network";',
        "    fontsize=11;",
        '    n0 [label="NIC MTU: 9000 or 1500"];',
        '    n1 [label="Cluster MTU: 50-100 below NIC"];',
        '    n2 [label="Bond: active-backup / balance-slb"];',
        '    n3 [label="VLANs: API, Ingress, Storage, Migration"];',
        "  }",
        "",
        "  subgraph cluster_nodes {",
        '    label="Worker nodes (HA)";',
        "    fontsize=11;",
    ]
    for i in range(1, n_show + 1):
        lines.append(f'    w{i} [label="Worker {i}\\n{worker_cores}c / {worker_memory_gib}GiB"];')
    if num_workers > n_show:
        lines.append(f'    w_etc [label="... +{num_workers - n_show} more", style=dashed];')
    lines.append("  }")
    lines.append("  n0 -> w1 [style=invis];")
    lines.append("}")
    return "\n".join(lines)
