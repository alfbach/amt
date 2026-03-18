# -*- coding: utf-8 -*-
"""
vCenter API client: connect to vCenter and fetch VM data for migration analysis.
Uses pyvmomi (vSphere API).
"""

import ssl
from typing import Optional

import pandas as pd

try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim

    PYVMOMI_AVAILABLE = True
except ImportError:
    PYVMOMI_AVAILABLE = False


def fetch_vms_from_vcenter(
    host: str,
    user: str,
    password: str,
    skip_ssl: bool = False,
    port: int = 443,
) -> dict:
    """
    Connect to vCenter and fetch VM data. Returns a dict compatible with rvtools_parser
    (e.g. {"vInfo": DataFrame}).
    """
    if not PYVMOMI_AVAILABLE:
        raise ImportError(
            "pyvmomi is required for vCenter live import. Install with: pip install pyvmomi"
        )

    host = host.strip()
    if not host:
        raise ValueError("vCenter host is required")
    if not user or not password:
        raise ValueError("Username and password are required")

    # Normalize host (remove protocol if present)
    if host.startswith("https://"):
        host = host[8:]
    elif host.startswith("http://"):
        host = host[7:]
    host = host.rstrip("/").split("/")[0]

    ssl_context = None
    if skip_ssl:
        ssl_context = ssl._create_unverified_context()

    si = SmartConnect(
        host=host,
        user=user,
        pwd=password,
        port=port,
        sslContext=ssl_context,
    )

    try:
        content = si.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.VirtualMachine]
        recursive = True
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive
        )

        rows = []
        for vm in container_view.view:
            try:
                row = _vm_to_row(vm, content)
                if row:
                    rows.append(row)
            except Exception:
                continue

        container_view.Destroy()
    finally:
        Disconnect(si)

    if not rows:
        return {"vInfo": pd.DataFrame()}

    df = pd.DataFrame(rows)
    return {"vInfo": df}


def _vm_to_row(vm, content) -> Optional[dict]:
    """Convert a pyvmomi VirtualMachine to a dict compatible with VINFO_COLUMNS."""
    try:
        summary = vm.summary
        config = summary.config
        runtime = summary.runtime
        storage = summary.storage
    except Exception:
        return None

    # Power state
    power_state = "unknown"
    if runtime and runtime.powerState:
        ps = str(runtime.powerState).lower()
        if "poweredon" in ps or "on" in ps:
            power_state = "poweredOn"
        elif "poweredoff" in ps or "off" in ps:
            power_state = "poweredOff"
        elif "suspended" in ps:
            power_state = "suspended"
        else:
            power_state = ps

    # Template
    is_template = config.template if config else False

    # CPUs
    cpus = int(config.numCpu) if config and config.numCpu else 0

    # Memory (MB)
    memory_mb = 0
    if config and config.memorySizeMB:
        memory_mb = int(config.memorySizeMB)

    # Storage: committed = in use, provisioned from disk devices
    provisioned_mb = 0
    in_use_mb = 0
    if storage:
        if storage.committed:
            in_use_mb = int(storage.committed / (1024 * 1024))
        if storage.uncommitted is not None and storage.committed is not None:
            provisioned_mb = int((storage.committed + storage.uncommitted) / (1024 * 1024))
        elif storage.committed:
            provisioned_mb = in_use_mb

    if provisioned_mb == 0 and vm.config and vm.config.hardware:
        for dev in vm.config.hardware.device:
            if hasattr(dev, "capacityInKB") and dev.capacityInKB:
                provisioned_mb += int(dev.capacityInKB / 1024)

    # Cluster / Host
    cluster_name = ""
    host_name = ""
    if runtime and runtime.host:
        host_obj = runtime.host
        host_name = host_obj.name if hasattr(host_obj, "name") else ""
        parent = host_obj.parent
        while parent:
            if isinstance(parent, vim.ClusterComputeResource):
                cluster_name = parent.name
                break
            parent = parent.parent if hasattr(parent, "parent") else None

    # Guest OS
    guest_os = ""
    if config and config.guestId:
        guest_os = config.guestId

    # Hardware version
    hw_version = ""
    if vm.config and vm.config.version:
        hw_version = vm.config.version

    return {
        "vm": config.name if config else "Unknown",
        "powerstate": power_state,
        "template": is_template,
        "cpus": cpus,
        "memory": memory_mb,
        "provisioned_mb": provisioned_mb,
        "in_use_mb": in_use_mb,
        "cluster": cluster_name,
        "host": host_name,
        "guest_os": guest_os,
        "hardware_version": hw_version,
    }
