# -*- coding: utf-8 -*-
"""
OS analysis: list guest operating systems from VMs and assess supportability
from Microsoft and Red Hat perspectives.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

# Microsoft Windows Server support (Extended Support End date)
# Source: https://learn.microsoft.com/lifecycle/products/
MS_SUPPORT = {
    "windows server 2025": ("supported", "2034", "Extended support"),
    "windows server 2022": ("supported", "2031", "Extended support"),
    "windows server 2019": ("supported", "2029", "Extended support"),
    "windows server 2016": ("supported", "2027", "Extended support"),
    "windows server 2012 r2": ("eol", "2023", "End of support"),
    "windows server 2012": ("eol", "2023", "End of support"),
    "windows server 2008 r2": ("eol", "2020", "End of support"),
    "windows server 2008": ("eol", "2020", "End of support"),
    "windows 11": ("supported", "2032", "Consumer support"),
    "windows 10": ("supported", "2025", "Consumer support"),
    "windows 8.1": ("eol", "2023", "End of support"),
    "windows 7": ("eol", "2020", "End of support"),
}

# Red Hat Enterprise Linux support
# Source: https://access.redhat.com/support/policy/updates/errata
RH_SUPPORT = {
    "rhel 10": ("supported", "2035", "Full support"),
    "rhel 9": ("supported", "2032", "Full support"),
    "rhel 8": ("supported", "2029", "Full support"),
    "rhel 7": ("maintenance", "2024", "ELS ended Jun 2024"),
    "rhel 6": ("eol", "2024", "Retired"),
    "rhel 5": ("eol", "2020", "Retired"),
    "centos stream 9": ("supported", "—", "Upstream of RHEL"),
    "centos stream 8": ("supported", "—", "Upstream of RHEL"),
    "centos 7": ("eol", "2024", "EOL June 2024"),
    "centos 8": ("eol", "2021", "EOL December 2021"),
    "rocky linux 9": ("supported", "—", "RHEL-compatible"),
    "rocky linux 8": ("supported", "—", "RHEL-compatible"),
    "almalinux 9": ("supported", "—", "RHEL-compatible"),
    "almalinux 8": ("supported", "—", "RHEL-compatible"),
}


def _normalize_os(guest_os: str) -> str:
    """Normalize guest OS string for matching."""
    if not guest_os or (isinstance(guest_os, float) and pd.isna(guest_os)):
        return ""
    s = str(guest_os).strip().lower()
    return s


def _match_ms_support(guest_os: str) -> tuple[str, str, str]:
    """Match OS to Microsoft support. Returns (status, date, note)."""
    s = _normalize_os(guest_os)
    if not s:
        return ("unknown", "—", "")
    # Check longer patterns first for specificity
    for pattern, (status, date, note) in sorted(MS_SUPPORT.items(), key=lambda x: -len(x[0])):
        if pattern in s:
            return (status, date, note)
    if "windows" in s or "win" in s:
        return ("unknown", "—", "Version not in database")
    return ("other", "—", "Not a Microsoft product")


def _match_rh_support(guest_os: str) -> tuple[str, str, str]:
    """Match OS to Red Hat support. Returns (status, date, note)."""
    s = _normalize_os(guest_os)
    if not s:
        return ("unknown", "—", "")
    for pattern, (status, date, note) in sorted(RH_SUPPORT.items(), key=lambda x: -len(x[0])):
        if pattern in s:
            return (status, date, note)
    if "rhel" in s or "red hat" in s or "centos" in s or "rocky" in s or "alma" in s or "fedora" in s:
        return ("unknown", "—", "Version not in database")
    return ("other", "—", "Not a Red Hat product")


def compute_os_analysis(vm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate VMs by guest OS and add Microsoft/Red Hat support columns.
    Returns DataFrame with: OS, VMs, vCPUs, Microsoft status, MS date, MS note, Red Hat status, RH date, RH note.
    """
    if vm_df.empty:
        return pd.DataFrame()

    # Resolve OS column - try standard name first, then common alternatives
    os_col = None
    for name in ("guest_os", "Guest OS", "OS", "GuestOS", "os", "Operating System"):
        if name in vm_df.columns:
            os_col = name
            break
    if not os_col:
        # Fallback: case-insensitive search for OS-related columns
        for col in vm_df.columns:
            c = str(col).lower()
            if c in ("guest_os", "guest os", "os", "guestos", "operating system"):
                os_col = col
                break
            if ("guest" in c or "operating" in c) and "os" in c:
                os_col = col
                break
    if not os_col:
        return pd.DataFrame()

    vm_df = vm_df.copy()
    vm_df["_os_norm"] = vm_df[os_col].fillna("").astype(str).str.strip()
    vm_df["_os_norm"] = vm_df["_os_norm"].replace("", "(unknown)")
    vm_df["_os_display"] = vm_df["_os_norm"]

    count_col = "vm" if "vm" in vm_df.columns else vm_df.columns[0]
    agg_dict = {count_col: "count"}
    if "cpus" in vm_df.columns:
        agg_dict["cpus"] = "sum"

    os_agg = vm_df.groupby("_os_display", dropna=False).agg(agg_dict).reset_index()
    rename_map = {count_col: "vms"}
    if "cpus" in agg_dict:
        rename_map["cpus"] = "vcpus"
    os_agg = os_agg.rename(columns=rename_map)
    if "vcpus" not in os_agg.columns:
        os_agg["vcpus"] = 0

    rows = []
    for _, row in os_agg.iterrows():
        os_name = row["_os_display"] if row["_os_display"] != "(unknown)" else ""
        ms_status, ms_date, ms_note = _match_ms_support(os_name)
        rh_status, rh_date, rh_note = _match_rh_support(os_name)
        rows.append({
            "os": os_name or "(unknown)",
            "vms": int(row["vms"]),
            "vcpus": int(row.get("vcpus", 0)),
            "ms_status": ms_status,
            "ms_date": ms_date,
            "ms_note": ms_note,
            "rh_status": rh_status,
            "rh_date": rh_date,
            "rh_note": rh_note,
        })

    return pd.DataFrame(rows)
