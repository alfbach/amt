"""
RVTools-Dateien (XLSX/CSV) einlesen und normalisieren.
Unterstützt vInfo, vVM und optionale Tabs (vDisk, vNic, vDatastore).
"""

import io
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd


# Bekannte Spaltennamen in RVTools (verschiedene Schreibweisen)
VINFO_COLUMNS = {
    "vm": ["VM", "vm", "Name", "Virtual Machine"],
    "powerstate": ["Powerstate", "powerstate", "Power State"],
    "template": ["Template", "template"],
    "cpus": ["CPUs", "CPUs:", "CPU", "cpus"],
    "memory": ["Memory", "memory", "Memory MB", "Memory MB:"],
    "provisioned_mb": ["Provisioned MB", "Provisioned MiB", "provisioned MB"],
    "in_use_mb": ["In use MB", "In use MiB", "In Use MB", "in use MB"],
    "cluster": ["Cluster", "cluster"],
    "host": ["Host", "host", "ESX Host"],
    "guest_os": [
        "OS according to configuration file",
        "OS according to the configuration file",
        "Guest OS",
        "GuestOS",
        "OS",
        "os",
        "Operating System",
        "OperatingSystem",
    ],
    "uuid": ["VM UUID", "UUID", "vm uuid"],
    "primary_ip": ["Primary IP", "Primary IP Address", "IP Address"],
    "folder": ["Folder", "folder"],
    "resource_pool": ["Resource pool", "Resource Pool", "resource pool"],
    "hardware_version": ["Hardware version", "HW Version", "hardware version"],
    "annotation": ["Annotation", "annotation", "Description"],
    "datacenter": ["Datacenter", "datacenter"],
    "vcenter": ["vCenter Server", "vCenter", "vcenter server"],
}


def _normalize_columns(df: pd.DataFrame, column_map: dict[str, list[str]]) -> pd.DataFrame:
    """DataFrame-Spalten auf einheitliche Namen mappen."""
    rename = {}
    for standard_name, variants in column_map.items():
        variants_lower = [v.lower() for v in variants]
        for col in df.columns:
            if col:
                col_clean = str(col).strip()
                if col_clean in variants or col_clean.lower() in variants_lower:
                    rename[col] = standard_name
                    break
    return df.rename(columns=rename)


def _excel_engine(suffix: str) -> str:
    """openpyxl für .xlsx, xlrd für altes .xls."""
    if suffix == ".xls":
        return "xlrd"
    return "openpyxl"


def _read_excel_sheets(source: Any, filename: str = "") -> dict[str, pd.DataFrame]:
    """Alle Sheets einer Excel-Datei einlesen (Pfad oder file-like)."""
    suffix = Path(filename).suffix.lower() if filename else ""
    if not suffix and isinstance(source, (str, Path)):
        suffix = Path(source).suffix.lower()
    if hasattr(source, "seek"):
        source.seek(0)
    return pd.read_excel(source, sheet_name=None, engine=_excel_engine(suffix))


def _read_csv(source: Any) -> pd.DataFrame:
    """CSV einlesen; UTF-8 mit Fallback auf Latin-1 (häufig bei RVTools)."""
    encodings = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
    last_err: Optional[Exception] = None
    for enc in encodings:
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, encoding=enc, on_bad_lines="skip")
        except UnicodeDecodeError as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise ValueError("CSV konnte nicht gelesen werden.")


def _sheets_from_excel(source: Any, filename: str = "") -> dict[str, pd.DataFrame]:
    sheets = _read_excel_sheets(source, filename=filename)
    result = {}
    for name, df in sheets.items():
        name_clean = str(name).strip()
        if name_clean and not df.empty:
            result[name_clean] = df
    return result


def load_rvtools_bytes(data: bytes, filename: str) -> dict:
    """
    RVTools-Export aus Bytes laden (z. B. Streamlit UploadedFile).
    Vermeidet temporäre Dateien – wichtig in OpenShift-Containern.
    """
    if not data:
        raise ValueError("Leere Datei.")
    name = filename or "export.csv"
    suffix = Path(name).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return _sheets_from_excel(io.BytesIO(data), filename=name)
    if suffix == ".csv":
        df = _read_csv(io.BytesIO(data))
        return {"vInfo": df} if not df.empty else {}
    raise ValueError("Nur .xlsx, .xls oder .csv werden unterstützt.")


def load_rvtools(path: Union[str, Path]) -> dict:
    """
    RVTools-Export laden. Akzeptiert:
    - .xlsx / .xls: alle Sheets (vInfo, vVM, vDisk, ...)
    - .csv: wird als vInfo-ähnliche Tabelle interpretiert
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")

    if path.suffix.lower() in (".xlsx", ".xls"):
        return _sheets_from_excel(path)

    if path.suffix.lower() == ".csv":
        with path.open("rb") as f:
            df = _read_csv(f)
        return {"vInfo": df} if not df.empty else {}

    raise ValueError("Nur .xlsx, .xls oder .csv werden unterstützt.")

def get_vm_data(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    VM-Daten aus vInfo oder vVM extrahieren und Spalten normalisieren.
    """
    df = None
    for sheet_name in ("vInfo", "vVM", "vinfo", "vvm"):
        if sheet_name in sheets:
            df = sheets[sheet_name].copy()
            break
    if df is None and sheets:
        # Fallback: erstes Sheet mit VM-ähnlichen Spalten
        for name, frame in sheets.items():
            cols_lower = [str(c).lower() for c in frame.columns]
            if "vm" in cols_lower or "cpu" in cols_lower or "memory" in cols_lower:
                df = frame.copy()
                break
    if df is None:
        return pd.DataFrame()

    df = _normalize_columns(df, VINFO_COLUMNS)

    # Numerische Spalten bereinigen
    for col in ["cpus", "memory", "provisioned_mb", "in_use_mb"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")

    return df


def filter_vms_for_migration(df: pd.DataFrame) -> pd.DataFrame:
    """Nur VMs die für Migration in Betracht kommen (keine Templates, ggf. powered on/off)."""
    if df.empty:
        return df
    out = df.copy()
    if "template" in out.columns:
        out = out[out["template"].astype(str).str.lower().isin(("false", "0", "no", ""))]
    return out.reset_index(drop=True)


def get_host_count(sheets: dict) -> int:
    """Number of ESXi hosts from vHost sheet if present, else 0."""
    for name in ("vHost", "vhost", "VHost"):
        if name in sheets:
            return max(0, len(sheets[name]))
    return 0


def get_host_count_from_vm_data(vm_df: pd.DataFrame) -> int:
    """Number of unique ESXi hosts from VM data (host column). For vCenter or RVTools without vHost."""
    if vm_df.empty or "host" not in vm_df.columns:
        return 0
    hosts = vm_df["host"].dropna().astype(str).str.strip()
    hosts = hosts[hosts.str.len() > 0]
    return max(0, hosts.nunique())
