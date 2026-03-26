# -*- coding: utf-8 -*-
"""
High Availability design and network diagram for OpenShift cluster.
Produces Graphviz DOT and recommended network settings.
"""

from typing import Any, Dict, List, Tuple


def get_ha_recommendations(
    workers_needed: int,
    ha_enabled: bool,
    ha_min_workers: int,
    odf_enabled: bool,
    t: Dict[str, str] = None,
) -> List[str]:
    """Return list of HA design recommendations (localized if t is provided)."""
    t = t or {}
    recs = []
    if not ha_enabled:
        recs.append(t.get("ha_rec_disabled", "HA is disabled. Enable for production to tolerate node failures."))
        return recs
    min_nodes = max(ha_min_workers, 3)
    if workers_needed < min_nodes and workers_needed > 0:
        recs.append(
            t.get("ha_rec_need_nodes", "For HA, use at least {min} worker nodes (current design: {w}).").format(
                min=min_nodes, w=workers_needed
            )
        )
    elif workers_needed >= min_nodes:
        recs.append(
            t.get("ha_rec_ok", "HA design: {w} worker nodes (≥ {min} for HA).").format(w=workers_needed, min=min_nodes)
        )
    recs.append(t.get("ha_rec_zones", "Spread worker nodes across availability zones or racks where possible."))
    recs.append(t.get("ha_rec_cp", "OpenShift control plane: 3 nodes (schedulable or dedicated) for HA."))
    if odf_enabled:
        recs.append(t.get("ha_rec_odf", "ODF requires minimum 3 nodes; replication across nodes for storage HA."))
    recs.append(t.get("ha_rec_bonding", "Use multiple NICs with bonding (active-backup or balance-slb) for network HA."))
    return recs


def get_network_settings(t: Dict[str, str] = None) -> List[Tuple[str, str]]:
    """Return recommended network settings as (label, value) for OpenShift + Virt + ODF."""
    t = t or {}
    return [
        (t.get("net_set_mtu", "NIC MTU"), t.get("net_set_mtu_val", "9000 (jumbo) for storage/VM traffic, or 1500 (standard)")),
        (t.get("net_set_cluster_mtu", "Cluster network MTU"), t.get("net_set_cluster_mtu_val", "50–100 bytes below NIC MTU (e.g. 8950 or 1450)")),
        (t.get("net_set_bonding", "Bonding"), t.get("net_set_bonding_val", "active-backup (fault tolerance) or balance-slb (load balance)")),
        (t.get("net_set_vlans", "VLANs / networks"), t.get("net_set_vlans_val", "API, Ingress, default pod, ODF/Storage, VM/Migration")),
        (t.get("net_set_mtv", "Migration network (MTV)"), t.get("net_set_mtv_val", "Dedicated VLAN or segment; MTU must match OpenShift")),
    ]


def build_topology_dot(
    num_workers: int,
    worker_cores: int,
    worker_memory_gib: int,
    t: Dict[str, str] = None,
) -> str:
    """Build Graphviz DOT for cluster topology and recommended network."""
    t = t or {}
    n_show = min(max(1, num_workers), 6)
    lbl_net = t.get("dot_label_network", "Recommended network")
    lbl_workers = t.get("dot_label_workers", "Worker nodes (HA)")
    lbl_more = t.get("dot_label_more", "... +{n} more")
    lines = [
        "digraph G {",
        "  rankdir=TB;",
        "  node [shape=box, style=rounded, fontname=Helvetica];",
        "  compound=true;",
        "",
        "  subgraph cluster_network {",
        f'    label="{lbl_net}";',
        "    fontsize=11;",
        '    n0 [label="NIC MTU: 9000 or 1500"];',
        '    n1 [label="Cluster MTU: 50-100 below NIC"];',
        '    n2 [label="Bond: active-backup / balance-slb"];',
        '    n3 [label="VLANs: API, Ingress, Storage, Migration"];',
        "  }",
        "",
        "  subgraph cluster_nodes {",
        f'    label="{lbl_workers}";',
        "    fontsize=11;",
    ]
    for i in range(1, n_show + 1):
        lines.append(f'    w{i} [label="Worker {i}\\n{worker_cores}c / {worker_memory_gib}GiB"];')
    if num_workers > n_show:
        lines.append(f'    w_etc [label="{lbl_more.format(n=num_workers - n_show)}", style=dashed];')
    lines.append("  }")
    lines.append("  n0 -> w1 [style=invis];")
    lines.append("}")
    return "\n".join(lines)
