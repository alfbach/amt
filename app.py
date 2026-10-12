# -*- coding: utf-8 -*-
"""
AlfsMigrationToolkit: RVTools analysis and migration plan VMware → OpenShift Virtualization.
Multi-language (EN/FR/DE), worker node config, cluster design, and cost estimation.
"""

import warnings

# urllib3 v2 + macOS LibreSSL: warn on import; must filter before any urllib3 load (do not import urllib3 here).
warnings.filterwarnings("ignore", message=r".*urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", message=r".*urllib3.*OpenSSL.*", category=UserWarning)

from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import analyze_all_vms, summary_stats
from os_analysis import compute_os_analysis
from cluster_design import (
    compute_cluster_design,
    compute_odf_design,
    compute_optimal_node_config,
    OPTIMIZE_CHEAP_MAX_CORES,
    OPTIMIZE_CHEAP_MAX_MEMORY_GIB,
)
from ha_network_diagram import build_topology_dot, get_ha_recommendations, get_network_settings
from i18n import get_translations
from migration_plan import build_migration_phases, generate_plan_markdown, generate_plan_with_risk_markdown
from risk_analysis import compute_risk_analysis
from rvtools_parser import (
    filter_vms_for_migration,
    get_vm_data,
    get_host_count,
    get_host_count_from_vm_data,
    load_rvtools_bytes,
)
try:
    from vcenter_client import fetch_vms_from_vcenter
    VCENTER_AVAILABLE = True
except ImportError:
    VCENTER_AVAILABLE = False
from cloud_baremetal import get_bare_metal_offerings
from cloud_regions import get_regions
from deploy_prototype import (
    build_install_config,
    build_azure_credentials_json,
    build_run_script,
    build_destroy_script,
    validate_cluster_name,
    validate_pull_secret,
)

st.set_page_config(
    page_title="AlfsMigrationToolkit",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apple-inspired styling (HIG: clarity, depth, deference)
st.markdown(
    "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'>",
    unsafe_allow_html=True,
)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    :root {
        --apple-blue: #007AFF;
        --apple-blue-hover: #0051D5;
        --apple-gray-1: #0D0D0F;
        --apple-gray-2: #4A4A4E;
        --apple-bg: #FFFFFF;
        --apple-bg-secondary: #F2F2F7;
        --apple-bg-tertiary: #D1D1D6;
    }
    * { font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Display', 'Segoe UI', sans-serif !important; }
    /* Base readability: larger body text */
    .stMarkdown, p, [data-testid="stMarkdown"] {
        font-size: 1.05rem !important;
        line-height: 1.6 !important;
        color: var(--apple-gray-1) !important;
    }
    h1 {
        color: var(--apple-gray-1) !important;
        font-weight: 600 !important;
        font-size: 1.95rem !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 0.5rem !important;
    }
    h2 {
        color: var(--apple-gray-1) !important;
        font-weight: 600 !important;
        font-size: 1.4rem !important;
        letter-spacing: -0.01em !important;
    }
    h3 {
        color: var(--apple-gray-1) !important;
        font-weight: 600 !important;
        font-size: 1.2rem !important;
    }
    [data-testid="stSidebar"] {
        background: var(--apple-bg-secondary) !important;
        border-right: 1px solid var(--apple-bg-tertiary) !important;
    }
    [data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stMarkdown {
        color: var(--apple-gray-1) !important;
        font-size: 1rem !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--apple-bg-tertiary) !important;
    }
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--apple-blue) !important;
        font-weight: 600 !important;
        font-size: 1.25rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--apple-gray-2) !important;
        font-weight: 500 !important;
        font-size: 1rem !important;
    }
    .streamlit-expanderHeader {
        background-color: var(--apple-bg-secondary) !important;
        border-radius: 10px !important;
        font-size: 1.05rem !important;
    }
    .streamlit-expanderContent {
        font-size: 1.05rem !important;
        line-height: 1.6 !important;
    }
    [data-testid="stDataFrame"] {
        border: 1.5px solid var(--apple-bg-tertiary) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        font-size: 1rem !important;
    }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
        font-size: 1rem !important;
        padding: 0.6rem 0.75rem !important;
    }
    [data-testid="stAlert"] {
        border-radius: 12px !important;
        border-left: 4px solid var(--apple-blue) !important;
    }
    a {
        color: var(--apple-blue) !important;
        font-weight: 500 !important;
    }
    a:hover {
        color: var(--apple-blue-hover) !important;
    }
    /* Input fields: larger, better visible, higher contrast */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        font-size: 1.1rem !important;
        padding: 0.75rem 1rem !important;
        min-height: 2.75rem !important;
        border: 1.5px solid var(--apple-bg-tertiary) !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        color: var(--apple-gray-1) !important;
        background-color: var(--apple-bg) !important;
    }
    .stTextArea textarea { min-height: 4rem !important; }
    .stTextInput label, .stNumberInput label, .stTextArea label, .stSelectbox label, .stCheckbox label {
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        color: var(--apple-gray-1) !important;
    }
    .stNumberInput input:focus, .stTextInput input:focus, .stTextArea textarea:focus {
        box-shadow: 0 0 0 2px var(--apple-blue) !important;
        border-color: var(--apple-blue) !important;
    }
    /* Radio, file uploader: larger, better contrast */
    .stRadio label, .stCheckbox label { font-size: 1.05rem !important; color: var(--apple-gray-1) !important; }
    [data-testid="stFileUploader"] {
        border: 1.5px solid var(--apple-bg-tertiary) !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        background: var(--apple-bg) !important;
    }
    [data-testid="stFileUploader"] label { font-size: 1.05rem !important; }
    /* Help text: readable */
    [data-testid="stForm"] small, .stTooltipIcon { font-size: 0.95rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [aria-selected="true"] {
        border-bottom: 2px solid var(--apple-blue) !important;
        color: var(--apple-blue) !important;
    }
    .vcenter-dialog-container {
        background: var(--apple-bg) !important;
        padding: 2rem !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08) !important;
        border: 1px solid var(--apple-bg-tertiary) !important;
        max-width: 420px !important;
        margin: 0 auto 0 !important;
        font-size: 1.1rem !important;
    }
    .vcenter-dialog-header {
        text-align: center;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--apple-bg-tertiary);
    }
    .vcenter-dialog-header h3 {
        margin: 0 !important;
        color: var(--apple-gray-1) !important;
        font-size: 1.5rem !important;
    }
    .vcenter-dialog-header i {
        color: var(--apple-blue);
        margin-right: 0.5rem;
    }
    [data-testid="column"]:has(.vcenter-dialog-container) {
        background: var(--apple-bg-secondary) !important;
        padding: 2rem !important;
        border-radius: 16px !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.04) !important;
        font-size: 1.1rem !important;
    }
    [data-testid="column"]:has(.vcenter-dialog-container) [data-testid="stForm"] label,
    [data-testid="column"]:has(.vcenter-dialog-container) [data-testid="stForm"] input {
        font-size: 1.1rem !important;
    }
    .deploy-cost-box {
        background: var(--apple-bg-secondary) !important;
        border: 1px solid var(--apple-bg-tertiary) !important;
        border-radius: 12px !important;
        padding: 1.25rem 1.5rem !important;
        margin: 0.75rem 0 !important;
    }
    .deploy-cost-box .cost-value {
        font-size: 1.75rem !important;
        font-weight: 600 !important;
        color: var(--apple-blue) !important;
    }
    .deploy-cost-box .cost-label {
        font-size: 1.05rem;
        color: var(--apple-gray-2);
    }
    .deploy-cost-box .cost-total {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        color: var(--apple-gray-1) !important;
        margin-top: 0.5rem;
    }
    .amt-menubar-title {
        font-weight: 600;
        font-size: 1.1rem;
        color: var(--apple-gray-1);
        letter-spacing: -0.02em;
    }
    .amt-menubar-tagline {
        font-size: 0.8rem;
        color: #8E8E93;
        margin-top: 0.15rem;
    }
    .amt-menubar-row {
        padding: 0.65rem 0 0.85rem 0;
        margin: -0.35rem 0 0.75rem 0;
        border-bottom: 1.5px solid var(--apple-bg-tertiary);
        background: linear-gradient(180deg, #FAFAFC 0%, #F2F2F7 100%);
        border-radius: 0 0 12px 12px;
    }
    .splash-wrap {
        max-width: 1000px;
        margin: 0.5rem auto 1.5rem auto;
        padding: 1.5rem 1.75rem 2rem 1.75rem;
        border-radius: 16px;
        border: 1px solid var(--apple-bg-tertiary);
        background: linear-gradient(165deg, #FFFFFF 0%, #F2F2F7 100%);
        box-shadow: 0 4px 24px rgba(0,0,0,0.06);
    }
    .splash-head {
        text-align: center;
        margin-bottom: 1rem;
    }
    .splash-head h1 {
        margin-bottom: 0.35rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Session state defaults
if "lang" not in st.session_state:
    st.session_state.lang = "en"
if "page" not in st.session_state:
    st.session_state.page = "analysis"
if "worker_cores" not in st.session_state:
    st.session_state.worker_cores = 64
if "worker_memory_gib" not in st.session_state:
    st.session_state.worker_memory_gib = 256
if "cpu_overcommit" not in st.session_state:
    st.session_state.cpu_overcommit = 2.0
if "memory_overcommit" not in st.session_state:
    st.session_state.memory_overcommit = 1.0
if "current_hosts" not in st.session_state:
    st.session_state.current_hosts = 0
if "current_power_w" not in st.session_state:
    st.session_state.current_power_w = 400
if "new_power_w" not in st.session_state:
    st.session_state.new_power_w = 280
if "rvtools_stats" not in st.session_state:
    st.session_state.rvtools_stats = None
if "rvtools_sheets" not in st.session_state:
    st.session_state.rvtools_sheets = None
if "odf_enabled" not in st.session_state:
    st.session_state.odf_enabled = True
if "odf_disks_per_node" not in st.session_state:
    st.session_state.odf_disks_per_node = 2
if "odf_disk_size_gb" not in st.session_state:
    st.session_state.odf_disk_size_gb = 1000
if "odf_replication_factor" not in st.session_state:
    st.session_state.odf_replication_factor = 3
if "odf_growth_buffer_pct" not in st.session_state:
    st.session_state.odf_growth_buffer_pct = 25.0
if "ha_enabled" not in st.session_state:
    st.session_state.ha_enabled = True
if "ha_min_workers" not in st.session_state:
    st.session_state.ha_min_workers = 3
if "odf_price_per_node_year" not in st.session_state:
    st.session_state.odf_price_per_node_year = 0.0
if "ov_price_per_node_year" not in st.session_state:
    st.session_state.ov_price_per_node_year = 0.0
if "splash_acknowledged" not in st.session_state:
    st.session_state.splash_acknowledged = False

# Language & translations (menubar + app)
lang_options = ["en", "de", "fr"]
lang_labels = {"en": "English", "de": "Deutsch", "fr": "Français"}
if "lang_select" not in st.session_state:
    st.session_state.lang_select = st.session_state.get("lang", "en")
if st.session_state.lang_select not in lang_options:
    st.session_state.lang_select = "en"
st.session_state.lang = st.session_state.lang_select
t = get_translations(st.session_state.lang)

# Splash screen (first session visit): license, disclaimer, feedback
if not st.session_state.splash_acknowledged:
    splash_img_path = Path(__file__).resolve().parent / "assets" / "splash.png"
    st.markdown("<div class='splash-wrap'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='splash-head'><h1>{t['splash_title']}</h1>"
        f"<p style='color:#8E8E93;font-size:1rem;margin:0'>{t['menubar_tagline']}</p></div>",
        unsafe_allow_html=True,
    )
    _, lang_row2, _ = st.columns([1, 2, 1])
    with lang_row2:
        st.selectbox(
            t["language"],
            options=lang_options,
            format_func=lambda x: lang_labels[x],
            key="lang_select",
            index=lang_options.index(st.session_state.lang_select)
            if st.session_state.lang_select in lang_options
            else 0,
        )
    st.session_state.lang = st.session_state.lang_select
    t = get_translations(st.session_state.lang)
    img_c, txt_c = st.columns([1, 1])
    with img_c:
        if splash_img_path.is_file():
            _pad_l, _img_25, _pad_r = st.columns([3, 2, 3])
            with _img_25:
                st.image(str(splash_img_path), use_container_width=True)
        else:
            st.empty()
    with txt_c:
        st.markdown(t["splash_intro"])
        st.markdown(t["splash_gpl2"])
        st.markdown(t["splash_disclaimer"])
        st.markdown(t["splash_feedback"])
    _, cont2, _ = st.columns([1, 2, 1])
    with cont2:
        if st.button(t["splash_continue"], type="primary", use_container_width=True, key="splash_continue_btn"):
            st.session_state.splash_acknowledged = True
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# Top menubar: title, language, context help
page_for_help = st.session_state.get("page_radio", st.session_state.get("page", "analysis"))
if page_for_help not in (
    "analysis",
    "os_analysis",
    "config",
    "cluster_design",
    "ha_diagram",
    "migration_plan",
    "deploy",
):
    page_for_help = "analysis"
help_key = f"help_page_{page_for_help}"
help_body = t.get(help_key, "")

st.markdown("<div class='amt-menubar-row'>", unsafe_allow_html=True)
mb1, mb2, mb3 = st.columns([3.2, 1.4, 1.4])
with mb1:
    st.markdown(
        f"<div class='amt-menubar-title'>{t['app_title']}</div>"
        f"<div class='amt-menubar-tagline'>{t['menubar_tagline']}</div>",
        unsafe_allow_html=True,
    )
with mb2:
    st.selectbox(
        t["language"],
        options=lang_options,
        format_func=lambda x: lang_labels[x],
        key="lang_select",
        index=lang_options.index(st.session_state.lang_select),
        label_visibility="collapsed",
    )
with mb3:
    if hasattr(st, "popover"):
        try:
            with st.popover(t["menu_help"], use_container_width=True):
                st.markdown(help_body)
        except TypeError:
            with st.popover(t["menu_help"]):
                st.markdown(help_body)
    else:
        with st.expander(t["menu_help"], expanded=False):
            st.markdown(help_body)
st.markdown("</div>", unsafe_allow_html=True)

st.session_state.lang = st.session_state.lang_select
t = get_translations(st.session_state.lang)

# Sidebar: Navigation only
with st.sidebar:
    st.divider()
    # Navigation labels with icon hints (icons shown on each page title)
    nav_pages = ["analysis", "os_analysis", "config", "cluster_design", "ha_diagram", "migration_plan", "deploy"]
    page = st.radio(
        "Navigation",
        nav_pages,
        format_func=lambda x: {
            "analysis": "Analysis",
            "os_analysis": t["tab_os_analysis"],
            "config": t["tab_config"],
            "cluster_design": t["tab_cluster_design"],
            "ha_diagram": t["tab_ha_diagram"],
            "migration_plan": t["tab_migration_plan"],
            "deploy": t["tab_deploy"],
        }[x],
        key="page_radio",
    )
    st.session_state.page = page

# ---- Configuration page ----
if st.session_state.page == "config":
    st.markdown(
        f"<h1><i class='fas fa-cog' style='color:#007AFF; margin-right:0.35em;'></i>{t['config_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["config_intro"])

    # Optimize button: find minimal nodes from workload
    stats = st.session_state.rvtools_stats
    total_vcpus = stats["total_vcpus"] if stats else 0
    total_memory_gib = stats["total_memory_gib"] if stats else 0.0
    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        if st.button(
            "🔧 " + t["config_optimize_btn"],
            help=t["config_optimize_help"],
            key="config_optimize_btn",
        ):
            if total_vcpus > 0 or total_memory_gib > 0:
                min_workers = st.session_state.get("ha_min_workers", 3) if st.session_state.get("ha_enabled", True) else 1
                opt_cores, opt_mem, opt_nodes = compute_optimal_node_config(
                    total_vcpus=total_vcpus,
                    total_memory_gib=total_memory_gib,
                    cpu_overcommit=float(st.session_state.cpu_overcommit),
                    memory_overcommit=float(st.session_state.memory_overcommit),
                    min_workers=min_workers,
                )
                st.session_state.worker_cores = opt_cores
                st.session_state.worker_memory_gib = opt_mem
                st.success(t["config_optimize_result"].format(cores=opt_cores, memory=opt_mem, nodes=opt_nodes))
            else:
                st.warning(t["config_optimize_no_data"])
    with opt_col2:
        if st.button(
            "💰 " + t["config_optimize_cheap_btn"],
            help=t["config_optimize_cheap_help"],
            key="config_optimize_cheap_btn",
        ):
            if total_vcpus > 0 or total_memory_gib > 0:
                min_workers = st.session_state.get("ha_min_workers", 3) if st.session_state.get("ha_enabled", True) else 1
                opt_cores, opt_mem, opt_nodes = compute_optimal_node_config(
                    total_vcpus=total_vcpus,
                    total_memory_gib=total_memory_gib,
                    cpu_overcommit=float(st.session_state.cpu_overcommit),
                    memory_overcommit=float(st.session_state.memory_overcommit),
                    min_workers=min_workers,
                    max_cores=OPTIMIZE_CHEAP_MAX_CORES,
                    max_memory_gib=OPTIMIZE_CHEAP_MAX_MEMORY_GIB,
                )
                st.session_state.worker_cores = opt_cores
                st.session_state.worker_memory_gib = opt_mem
                st.success(t["config_optimize_cheap_result"].format(cores=opt_cores, memory=opt_mem, nodes=opt_nodes))
            else:
                st.warning(t["config_optimize_no_data"])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader(t["config_target_hw"])
        st.session_state.worker_cores = st.number_input(
            t["worker_cores"],
            min_value=1,
            max_value=256,
            value=st.session_state.worker_cores,
            help=t["worker_cores_help"],
        )
        st.session_state.worker_memory_gib = st.number_input(
            t["worker_memory_gib"],
            min_value=1,
            max_value=2048,
            value=st.session_state.worker_memory_gib,
            help=t["worker_memory_help"],
        )
        st.session_state.cpu_overcommit = st.number_input(
            t["cpu_overcommit"],
            min_value=1.0,
            max_value=10.0,
            value=float(st.session_state.cpu_overcommit),
            step=0.25,
            help=t["cpu_overcommit_help"],
        )
        st.session_state.memory_overcommit = st.number_input(
            t["memory_overcommit"],
            min_value=1.0,
            max_value=3.0,
            value=float(st.session_state.memory_overcommit),
            step=0.1,
            help=t["memory_overcommit_help"],
        )
    with c2:
        st.subheader(t["current_infra"])
        current_hosts_val = st.session_state.current_hosts
        st.session_state.current_hosts = st.number_input(
            t["current_hosts"],
            min_value=0,
            max_value=10000,
            value=min(current_hosts_val, 10000),
            help=t["current_hosts_help"],
        )
        st.session_state.current_power_w = st.number_input(
            t["current_power_w"],
            min_value=0,
            max_value=2000,
            value=st.session_state.current_power_w,
            help=t["current_power_help"],
        )
        st.session_state.new_power_w = st.number_input(
            t["new_power_w"],
            min_value=0,
            max_value=2000,
            value=st.session_state.new_power_w,
            help=t["new_power_help"],
        )
    st.divider()
    st.subheader(t["odf_section"])
    st.caption(t["odf_section_caption"])
    storage_type = st.radio(
        t["storage_type"],
        options=["odf", "external"],
        format_func=lambda x: t["storage_type_odf"] if x == "odf" else t["storage_type_external"],
        index=0 if st.session_state.odf_enabled else 1,
        horizontal=True,
        key="storage_type_radio",
    )
    st.session_state.odf_enabled = storage_type == "odf"

    if st.session_state.odf_enabled:
        with st.expander(t["odf_hyperconverged_config"], expanded=True):
            st.markdown(t["odf_hyperconverged_intro"])
            oc1, oc2, oc3 = st.columns(3)
            with oc1:
                st.session_state.odf_disks_per_node = st.number_input(
                    t["odf_disks_per_node"],
                    min_value=1,
                    max_value=24,
                    value=st.session_state.odf_disks_per_node,
                    help=t["odf_disks_help"],
                )
                st.session_state.odf_disk_size_gb = st.number_input(
                    t["odf_disk_size_gb"],
                    min_value=512,
                    max_value=16000,
                    value=st.session_state.odf_disk_size_gb,
                    step=100,
                    help=t["odf_disk_size_help"],
                )
            with oc2:
                repl = st.selectbox(
                    t["odf_replication"],
                    options=[2, 3],
                    index=[2, 3].index(st.session_state.odf_replication_factor) if st.session_state.odf_replication_factor in (2, 3) else 1,
                    help=t["odf_replication_help"],
                )
                st.session_state.odf_replication_factor = repl
                st.session_state.odf_growth_buffer_pct = st.number_input(
                    t["odf_growth_buffer"],
                    min_value=10,
                    max_value=50,
                    value=int(st.session_state.odf_growth_buffer_pct),
                    step=5,
                    help=t["odf_growth_buffer_help"],
                )
            with oc3:
                stats_cfg = st.session_state.rvtools_stats
                total_vcpus_cfg = stats_cfg["total_vcpus"] if stats_cfg else 0
                total_mem_cfg = stats_cfg["total_memory_gib"] if stats_cfg else 0.0
                min_w = st.session_state.get("ha_min_workers", 3) if st.session_state.get("ha_enabled", True) else 1
                if stats_cfg and (total_vcpus_cfg or total_mem_cfg):
                    design_cfg = compute_cluster_design(
                        total_vcpus=total_vcpus_cfg,
                        total_memory_gib=total_mem_cfg,
                        worker_cores=st.session_state.worker_cores,
                        worker_memory_gib=st.session_state.worker_memory_gib,
                        cpu_overcommit=st.session_state.cpu_overcommit,
                        memory_overcommit=st.session_state.memory_overcommit,
                        min_workers=min_w,
                    )
                    num_nodes = design_cfg.workers_needed
                else:
                    num_nodes = max(3, min_w)
                raw = st.session_state.odf_disks_per_node * st.session_state.odf_disk_size_gb * num_nodes
                usable = raw / st.session_state.odf_replication_factor * (1 - st.session_state.odf_growth_buffer_pct / 100)
                st.metric(t["odf_preview_raw"].format(nodes=num_nodes), f"{raw:,.0f} GB")
                st.metric(t["odf_preview_usable"], f"{usable:,.0f} GB")
    else:
        st.info(t["storage_type_external_note"])
    st.divider()
    st.subheader(t["ha_section"])
    st.session_state.ha_enabled = st.checkbox(
        t["ha_enable"],
        value=st.session_state.ha_enabled,
        help=t["ha_enable_help"],
    )
    if st.session_state.ha_enabled:
        st.session_state.ha_min_workers = st.number_input(
            t["ha_min_workers"],
            min_value=2,
            max_value=20,
            value=st.session_state.ha_min_workers,
            help=t["ha_min_workers_help"],
        )
    st.divider()
    st.subheader(t["subscription_section"])
    st.caption(t["subscription_caption"])
    sub1, sub2 = st.columns(2)
    with sub1:
        st.session_state.odf_price_per_node_year = st.number_input(
            t["subscription_odf_per_node"],
            min_value=0.0,
            max_value=100000.0,
            value=float(st.session_state.odf_price_per_node_year),
            step=10.0,
            help=t["subscription_odf_help"],
        )
    with sub2:
        st.session_state.ov_price_per_node_year = st.number_input(
            t["subscription_ov_per_node"],
            min_value=0.0,
            max_value=100000.0,
            value=float(st.session_state.ov_price_per_node_year),
            step=10.0,
            help=t["subscription_ov_help"],
        )
    st.success(t["config_saved"])
    st.stop()

# ---- OS Analysis page ----
if st.session_state.page == "os_analysis":
    st.markdown(
        f"<h1><i class='fas fa-desktop' style='color:#007AFF; margin-right:0.35em;'></i>{t['os_analysis_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["os_analysis_intro"])

    sheets = st.session_state.rvtools_sheets
    if not sheets:
        st.info(t["os_analysis_no_data"])
        st.stop()

    vm_df_os = get_vm_data(sheets)
    vm_df_os = filter_vms_for_migration(vm_df_os)
    if vm_df_os.empty:
        st.warning(t["no_vm_data"])
        st.stop()

    # Filter by selected clusters (from Analysis page)
    selected = st.session_state.get("selected_clusters")
    if selected is not None and "cluster" in vm_df_os.columns:
        vm_df_os["_cluster_norm"] = vm_df_os["cluster"].fillna("").astype(str).str.strip().replace("", "(unassigned)")
        vm_df_os = vm_df_os[vm_df_os["_cluster_norm"].isin(selected)].drop(columns=["_cluster_norm"], errors="ignore")
    if vm_df_os.empty:
        st.warning(t["os_analysis_no_clusters_selected"])
        st.stop()

    os_df = compute_os_analysis(vm_df_os)
    if os_df.empty:
        st.warning(t["os_analysis_no_os_data"])
        st.stop()

    st.subheader(t["os_analysis_table_title"])
    sel = st.session_state.get("selected_clusters")
    if sel:
        st.caption(t["os_analysis_table_caption"] + " " + t["os_analysis_selected_clusters"].format(clusters=", ".join(sorted(sel))))
    else:
        st.caption(t["os_analysis_table_caption"])
    os_display = os_df.rename(columns={
        "os": t["os_analysis_col_os"],
        "vms": t["os_analysis_col_vms"],
        "vcpus": t["os_analysis_col_vcpus"],
        "ms_status": t["os_analysis_col_ms_status"],
        "ms_date": t["os_analysis_col_ms_date"],
        "ms_note": t["os_analysis_col_ms_note"],
        "rh_status": t["os_analysis_col_rh_status"],
        "rh_date": t["os_analysis_col_rh_date"],
        "rh_note": t["os_analysis_col_rh_note"],
    })
    st.dataframe(os_display, width="stretch", hide_index=True)

    st.subheader(t["os_analysis_legend_title"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**" + t["os_analysis_ms_legend"] + "**")
        st.markdown(t["os_analysis_legend_supported"])
        st.markdown(t["os_analysis_legend_maintenance"])
        st.markdown(t["os_analysis_legend_eol"])
        st.markdown(t["os_analysis_legend_other"])
    with c2:
        st.markdown("**" + t["os_analysis_rh_legend"] + "**")
        st.markdown(t["os_analysis_legend_supported"])
        st.markdown(t["os_analysis_legend_maintenance"])
        st.markdown(t["os_analysis_legend_eol"])
        st.markdown(t["os_analysis_legend_other"])

    st.download_button(
        label="📥 " + t["os_analysis_download"],
        data=os_display.to_csv(index=False).encode("utf-8"),
        file_name="os-analysis.csv",
        mime="text/csv",
        key="os_analysis_download_btn",
    )
    st.stop()

# ---- Cluster Design & Savings page ----
if st.session_state.page == "cluster_design":
    st.markdown(
        f"<h1><i class='fas fa-sitemap' style='color:#007AFF; margin-right:0.35em;'></i>{t['cluster_design_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["cluster_design_intro"])

    stats = st.session_state.rvtools_stats
    sheets = st.session_state.rvtools_sheets
    total_vcpus = stats["total_vcpus"] if stats else 0
    total_memory_gib = stats["total_memory_gib"] if stats else 0.0
    current_hosts = st.session_state.current_hosts or 0
    if sheets and current_hosts == 0:
        current_hosts = get_host_count(sheets)

    if not stats and (total_vcpus == 0 and total_memory_gib == 0):
        st.info(t["no_workers_calc"])
        design = None
    else:
        design = compute_cluster_design(
            total_vcpus=total_vcpus,
            total_memory_gib=total_memory_gib,
            worker_cores=st.session_state.worker_cores,
            worker_memory_gib=st.session_state.worker_memory_gib,
            cpu_overcommit=st.session_state.cpu_overcommit,
            memory_overcommit=st.session_state.memory_overcommit,
            current_hosts=current_hosts,
            current_power_w=st.session_state.current_power_w,
            new_power_w=st.session_state.new_power_w,
        )

    if design:
        st.subheader(t["workload_from_rvtools"])
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("vCPUs", design.total_vcpus)
        with col2:
            st.metric("RAM (GiB)", f"{design.total_memory_gib:.1f}")
        with col3:
            st.metric(t["current_hosts"], design.current_hosts or "–")

        st.subheader(t["design_target"])
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t["workers_needed"], design.workers_needed)
        with col2:
            st.metric(t["cpu_util"], f"{design.cpu_utilization_pct}%")
        with col3:
            st.metric(t["memory_util"], f"{design.memory_utilization_pct}%")
        with col4:
            st.metric(t["cores_per_node"], f"{design.worker_cores} × {design.workers_needed}")

        st.subheader(t["savings_title"])
        s1, s2 = st.columns(2)
        with s1:
            st.markdown("**" + t["density_savings"] + "**")
            st.caption(t["density_desc"])
            st.metric(
                t["fewer_servers"],
                f"{design.density_reduction} ({design.density_reduction_pct}%)" if design.current_hosts else "–",
            )
        with s2:
            st.markdown("**" + t["power_savings"] + "**")
            st.caption(t["power_desc"])
            st.metric(t["power_current_kw"], f"{design.power_current_kw:.1f} kW")
            st.metric(t["power_new_kw"], f"{design.power_new_kw:.1f} kW")
            st.metric(t["power_reduction"], f"{design.power_reduction_kw:.1f} kW ({design.power_reduction_pct}%)" if design.power_current_kw else "–")

        odf_price = float(st.session_state.get("odf_price_per_node_year", 0) or 0)
        ov_price = float(st.session_state.get("ov_price_per_node_year", 0) or 0)
        if odf_price > 0 or ov_price > 0:
            total_nodes = design.workers_needed
            price_per_node = odf_price + ov_price
            total_year = total_nodes * price_per_node
            st.divider()
            st.subheader(t["subscription_estimate_title"])
            st.caption(t["subscription_estimate_caption"])
            sub_c1, sub_c2, sub_c3, sub_c4 = st.columns(4)
            with sub_c1:
                st.metric(t["subscription_total_nodes"], f"{total_nodes:.0f}")
            with sub_c2:
                st.metric(t["subscription_per_node_year"], f"{price_per_node:,.0f} $" if price_per_node else "–")
            with sub_c3:
                st.metric(t["subscription_total_year"], f"{total_year:,.0f} $" if total_year else "–")
            with sub_c4:
                st.metric(t["subscription_total_month"], f"{total_year / 12:,.0f} $" if total_year else "–")

        if st.session_state.get("odf_enabled", True) and stats:
            total_storage_gb = stats.get("total_storage_gb", 0) or 0
            odf_design = compute_odf_design(
                workload_storage_gb=total_storage_gb,
                num_worker_nodes=design.workers_needed,
                disks_per_node=st.session_state.get("odf_disks_per_node", 2),
                disk_size_gb=float(st.session_state.get("odf_disk_size_gb", 1000)),
                replication_factor=int(st.session_state.get("odf_replication_factor", 3)),
                growth_buffer_pct=float(st.session_state.get("odf_growth_buffer_pct", 25)),
            )
            st.divider()
            st.subheader(t["odf_design_title"])
            st.caption(t["odf_caption"])
            o1, o2, o3, o4 = st.columns(4)
            with o1:
                st.metric(t["odf_workload_storage"], f"{odf_design.workload_storage_gb:.0f} GB")
            with o2:
                st.metric(t["odf_raw_total"], f"{odf_design.raw_total_gb:.0f} GB")
            with o3:
                st.metric(t["odf_usable_buffer"], f"{odf_design.usable_after_buffer_gb:.0f} GB")
            with o4:
                st.metric(t["odf_sufficient"], "✓" if odf_design.sufficient else "✗")
            st.metric(t["odf_utilization"], f"{odf_design.utilization_pct}%")
            st.markdown("**" + t["odf_recommendation"] + ":** " + odf_design.recommendation)
    st.stop()

# ---- HA & Network diagram page ----
if st.session_state.page == "ha_diagram":
    st.markdown(
        f"<h1><i class='fas fa-shield-halved' style='color:#007AFF; margin-right:0.35em;'></i>{t['ha_diagram_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["ha_diagram_intro"])

    stats = st.session_state.rvtools_stats
    total_vcpus = stats["total_vcpus"] if stats else 0
    total_memory_gib = stats["total_memory_gib"] if stats else 0.0
    current_hosts = st.session_state.current_hosts or 0
    if st.session_state.rvtools_sheets:
        current_hosts = current_hosts or get_host_count(st.session_state.rvtools_sheets)

    if stats and (total_vcpus or total_memory_gib):
        design = compute_cluster_design(
            total_vcpus=total_vcpus,
            total_memory_gib=total_memory_gib,
            worker_cores=st.session_state.worker_cores,
            worker_memory_gib=st.session_state.worker_memory_gib,
            cpu_overcommit=st.session_state.cpu_overcommit,
            memory_overcommit=st.session_state.memory_overcommit,
            current_hosts=current_hosts,
            current_power_w=st.session_state.current_power_w,
            new_power_w=st.session_state.new_power_w,
        )
        workers_needed = design.workers_needed
    else:
        workers_needed = max(3, st.session_state.ha_min_workers)

    ha_recs = get_ha_recommendations(
        workers_needed=workers_needed,
        ha_enabled=st.session_state.get("ha_enabled", True),
        ha_min_workers=st.session_state.get("ha_min_workers", 3),
        odf_enabled=st.session_state.get("odf_enabled", True),
        t=t,
    )
    st.subheader(t["ha_recommendations"])
    for rec in ha_recs:
        st.markdown("- " + rec)

    st.subheader(t["network_settings_table"])
    network_settings = get_network_settings(t)
    st.dataframe(
        pd.DataFrame(network_settings, columns=[t["net_col_setting"], t["net_col_recommended"]]),
        width="stretch",
        hide_index=True,
    )

    st.subheader(t["topology_diagram"])
    dot = build_topology_dot(
        num_workers=workers_needed,
        worker_cores=st.session_state.worker_cores,
        worker_memory_gib=st.session_state.worker_memory_gib,
        t=t,
    )
    try:
        st.graphviz_chart(dot)
    except Exception:
        st.code(dot, language="dot")
        st.caption(t["ha_diagram_fallback"])
    st.stop()

# ---- Migration plan & risk analysis page ----
if st.session_state.page == "migration_plan":
    st.markdown(
        f"<h1><i class='fas fa-clipboard-list' style='color:#007AFF; margin-right:0.35em;'></i>{t['migration_plan_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["migration_plan_intro"])

    sheets = st.session_state.rvtools_sheets
    stats = st.session_state.rvtools_stats

    if not sheets or not stats:
        st.info(t["no_workers_calc"])
        st.stop()

    vm_df = get_vm_data(sheets)
    vm_df = filter_vms_for_migration(vm_df)
    if vm_df.empty:
        st.warning(t["no_vm_data"])
        st.stop()

    recommendations = analyze_all_vms(vm_df)
    phases = build_migration_phases(recommendations, t)
    global_risks, phase_risks, risk_summary = compute_risk_analysis(recommendations, phases, stats, t)

    st.subheader(t["migration_phases"])
    for i, p in enumerate(phases):
        with st.expander(
            f"{p.name} — {len(p.vms)} " + t["vms"] + f" · {p.duration_estimate}",
            expanded=(i == 0),
        ):
            st.write(p.description)
            st.markdown("**" + t["prerequisites"] + "**")
            for pre in p.prerequisites:
                st.markdown(f"- {pre}")
            st.markdown("**" + t["risks"] + "**")
            for r in p.risks:
                st.markdown(f"- {r}")
            if p.vms:
                st.markdown("**" + t["vms"] + ":**")
                st.markdown("\n".join(f"- {v}" for v in p.vms[:25]) + ("\n- …" if len(p.vms) > 25 else ""))

    st.divider()
    st.subheader(t["risk_analysis_title"])
    overall = risk_summary.get("global_risk_level", "medium")
    overall_label = t.get(f"risk_level_{overall}", overall)
    st.metric(t["risk_overall"], overall_label)
    st.caption(f"{t['risk_high']}: {risk_summary.get('high_risks', 0)} · {t['risk_medium']}: {risk_summary.get('medium_risks', 0)} · {t['risk_low']}: {risk_summary.get('low_risks', 0)}")

    st.markdown("**" + t["risk_global"] + "**")
    risk_df = pd.DataFrame([
        {
            t["risk_category"]: r.category,
            t["risk_level"]: t.get(f"risk_level_{r.level}", r.level),
            t["risk_description"]: r.description,
            t["risk_mitigation"]: r.mitigation,
        }
        for r in global_risks
    ])
    st.dataframe(risk_df, width="stretch", hide_index=True)

    st.markdown("**" + t["risk_per_phase"] + "**")
    for pr in phase_risks:
        lvl = t.get(f"risk_level_{pr.level}", pr.level)
        st.markdown(f"- **{pr.phase_name}**: {lvl} ({pr.vm_count} " + t["vms"] + ")")
        for r in pr.risks:
            st.caption(f"  {r.description} — {r.mitigation}")

    plan_with_risk_md = generate_plan_with_risk_markdown(
        sheets, recommendations, stats, global_risks, phase_risks, risk_summary, t
    )
    st.download_button(
        label="📥 " + t["download_plan_with_risk"],
        data=plan_with_risk_md,
        file_name="migration-plan-and-risk.md",
        mime="text/markdown",
    )
    st.stop()

# ---- Deploy prototype cluster page ----
if st.session_state.page == "deploy":
    st.markdown(
        f"<h1><i class='fas fa-cloud-arrow-up' style='color:#007AFF; margin-right:0.35em;'></i>{t['deploy_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["deploy_intro"])
    st.warning(t["deploy_credentials_warning"])

    pilot_deployment = st.checkbox(
        t["deploy_pilot_mode"],
        value=st.session_state.get("deploy_pilot_mode", False),
        help=t["deploy_pilot_mode_help"],
        key="deploy_pilot_mode_check",
    )
    st.session_state.deploy_pilot_mode = pilot_deployment
    if pilot_deployment:
        st.caption(t["deploy_pilot_mode_caption"])

    platform_options = ["baremetal"] if pilot_deployment else ["aws", "azure", "ibmcloud", "baremetal"]
    platform_labels = {
        "aws": t["deploy_platform_aws"],
        "azure": t["deploy_platform_azure"],
        "ibmcloud": t["deploy_platform_ibmcloud"],
        "baremetal": t["deploy_platform_baremetal"],
    }
    platform_icons = {
        "aws": "fab fa-aws",
        "azure": "fab fa-microsoft",
        "ibmcloud": "fab fa-ibm",
        "baremetal": "fas fa-server",
    }
    platform = st.selectbox(
        t["deploy_platform"],
        options=platform_options,
        format_func=lambda x: platform_labels[x],
        key="deploy_platform_select",
    )
    st.markdown(
        f"<p style='font-size:1.1rem; color: #8E8E93; margin-top:-0.5rem; margin-bottom:1rem;'>"
        f"<i class='{platform_icons.get(platform, 'fas fa-cloud')}' style='color: #007AFF; margin-right:0.35em; font-size:1.25rem;'></i>"
        f"<strong>{platform_labels.get(platform, platform)}</strong></p>",
        unsafe_allow_html=True,
    )

    pull_secret_file = st.file_uploader(
        t["deploy_pull_secret"],
        type=["json", "txt"],
        help=t["deploy_pull_secret_help"],
        key="deploy_pull_secret_upload",
    )
    pull_secret_content = ""
    if pull_secret_file:
        try:
            pull_secret_content = pull_secret_file.read().decode("utf-8", errors="replace")
        except Exception:
            pull_secret_content = ""

    col1, col2 = st.columns(2)
    with col1:
        cluster_name = st.text_input(
            t["deploy_cluster_name"],
            value=st.session_state.get("deploy_cluster_name", "my-cluster"),
            help=t["deploy_cluster_name_help"],
            key="deploy_cluster_name_input",
        )
        st.session_state.deploy_cluster_name = cluster_name
    with col2:
        base_domain = st.text_input(
            t["deploy_base_domain"],
            value=st.session_state.get("deploy_base_domain", "example.com"),
            help=t["deploy_base_domain_help"],
            key="deploy_base_domain_input",
        )
        st.session_state.deploy_base_domain = base_domain

    ssh_key = st.text_area(
        t["deploy_ssh_key"],
        value=st.session_state.get("deploy_ssh_key", ""),
        help=t["deploy_ssh_key_help"],
        key="deploy_ssh_key_input",
        height=100,
    )

    st.markdown(
        f"<h3><i class='{platform_icons.get(platform, 'fas fa-cloud')}' style='color: #007AFF; margin-right:0.25em;'></i>"
        f"{platform_labels.get(platform, platform)}</h3>",
        unsafe_allow_html=True,
    )
    aws_region = aws_access_key = aws_secret_key = None
    azure_region = azure_subscription = azure_tenant = azure_client_id = azure_client_secret = azure_resource_group = None
    ibm_region = ibm_api_key = None
    architecture = None

    use_bare_metal = None
    bare_metal_type = None
    if platform == "aws":
        aws_regions = get_regions("aws")
        aws_region = st.selectbox(
            t["deploy_aws_region"],
            options=[r[0] for r in aws_regions],
            format_func=lambda x: next((r[1] for r in aws_regions if r[0] == x), x),
            index=0 if aws_regions else 0,
            key="deploy_aws_region",
        )
        c1, c2 = st.columns(2)
        with c1:
            aws_access_key = st.text_input(t["deploy_aws_access_key"], type="password", key="deploy_aws_access_key")
        with c2:
            aws_secret_key = st.text_input(t["deploy_aws_secret_key"], type="password", key="deploy_aws_secret_key")
        use_bare_metal = st.checkbox(t["deploy_use_bare_metal"], key="deploy_aws_bare_metal")
        if use_bare_metal:
            offerings, err = get_bare_metal_offerings(
                "aws",
                region=aws_region,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
            )
            if err:
                st.caption(t["deploy_bare_metal_fallback"].format(err=err))
            opts_dict = {o[0]: f"{o[1]} — {o[2]}" for o in offerings}
            cost_dict = {o[0]: o[3] for o in offerings if len(o) > 3 and o[3] is not None}
            bare_metal_type = st.selectbox(
                t["deploy_bare_metal_select"],
                options=list(opts_dict.keys()),
                format_func=lambda x: opts_dict.get(x, x),
                key="deploy_aws_bare_metal_type",
            )
            if bare_metal_type and bare_metal_type in cost_dict:
                num_nodes = st.number_input(
                    t["deploy_nodes_count"],
                    min_value=1,
                    max_value=100,
                    value=3,
                    help=t["deploy_nodes_count_help"],
                    key="deploy_aws_nodes",
                )
                cost_per_hour = cost_dict[bare_metal_type]
                cost_per_node_day = cost_per_hour * 24
                cost_total_day = cost_per_node_day * num_nodes
                cost_total_month = cost_total_day * 30
                st.markdown(
                    f'<div class="deploy-cost-box">'
                    f'<div class="cost-label">{t["deploy_cost_per_node"]}</div>'
                    f'<div class="cost-value">${cost_per_node_day:.0f} / {t["deploy_day"]}</div>'
                    f'<div class="cost-total">{t["deploy_cost_total_day"]}: {t["deploy_cost_value"].format(cost=f"${cost_total_day:.0f}")}</div>'
                    f'<div class="cost-total">{t["deploy_cost_total_month"]}: {t["deploy_cost_value"].format(cost=f"${cost_total_month:.0f}")}</div>'
                    f'<div class="cost-label" style="margin-top:0.5rem; font-size:0.9rem;">{t["deploy_cost_note_aws"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    elif platform == "azure":
        azure_regions = get_regions("azure")
        azure_region = st.selectbox(
            t["deploy_azure_region"],
            options=[r[0] for r in azure_regions],
            format_func=lambda x: next((r[1] for r in azure_regions if r[0] == x), x),
            index=0,
            key="deploy_azure_region",
        )
        azure_resource_group = st.text_input(t["deploy_azure_resource_group"], value="os4-common", key="deploy_azure_rg")
        azure_subscription = st.text_input(t["deploy_azure_subscription"], type="password", key="deploy_azure_sub")
        azure_tenant = st.text_input(t["deploy_azure_tenant"], type="password", key="deploy_azure_tenant")
        azure_client_id = st.text_input(t["deploy_azure_client_id"], type="password", key="deploy_azure_cid")
        azure_client_secret = st.text_input(t["deploy_azure_client_secret"], type="password", key="deploy_azure_secret")
        use_bare_metal = st.checkbox(t["deploy_use_bare_metal"], key="deploy_azure_bare_metal")
        if use_bare_metal:
            offerings, _ = get_bare_metal_offerings("azure", region=azure_region)
            opts_dict = {o[0]: f"{o[1]} — {o[2]}" for o in offerings}
            cost_dict = {o[0]: o[3] for o in offerings if len(o) > 3 and o[3] is not None}
            bare_metal_type = st.selectbox(
                t["deploy_bare_metal_select"],
                options=list(opts_dict.keys()),
                format_func=lambda x: opts_dict.get(x, x),
                key="deploy_azure_bare_metal_type",
            )
            if bare_metal_type and bare_metal_type in cost_dict:
                num_nodes = st.number_input(
                    t["deploy_nodes_count"],
                    min_value=1,
                    max_value=100,
                    value=3,
                    help=t["deploy_nodes_count_help"],
                    key="deploy_azure_nodes",
                )
                cost_per_hour = cost_dict[bare_metal_type]
                cost_per_node_day = cost_per_hour * 24
                cost_total_day = cost_per_node_day * num_nodes
                cost_total_month = cost_total_day * 30
                st.markdown(
                    f'<div class="deploy-cost-box">'
                    f'<div class="cost-label">{t["deploy_cost_per_node"]}</div>'
                    f'<div class="cost-value">${cost_per_node_day:.0f} / {t["deploy_day"]}</div>'
                    f'<div class="cost-total">{t["deploy_cost_total_day"]}: {t["deploy_cost_value"].format(cost=f"${cost_total_day:.0f}")}</div>'
                    f'<div class="cost-total">{t["deploy_cost_total_month"]}: {t["deploy_cost_value"].format(cost=f"${cost_total_month:.0f}")}</div>'
                    f'<div class="cost-label" style="margin-top:0.5rem; font-size:0.9rem;">{t["deploy_cost_note_azure"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    elif platform == "ibmcloud":
        ibm_regions = get_regions("ibmcloud")
        c1, c2 = st.columns(2)
        with c1:
            ibm_region = st.selectbox(
                t["deploy_ibm_region"],
                options=[r[0] for r in ibm_regions],
                format_func=lambda x: next((r[1] for r in ibm_regions if r[0] == x), x),
                index=0,
                key="deploy_ibm_region",
            )
        with c2:
            ibm_api_key = st.text_input(t["deploy_ibm_api_key"], type="password", key="deploy_ibm_apikey")
        use_bare_metal = st.checkbox(t["deploy_use_bare_metal"], key="deploy_ibm_bare_metal")
        if use_bare_metal:
            offerings, _ = get_bare_metal_offerings(
                "ibmcloud",
                region=ibm_region,
                ibm_api_key=ibm_api_key,
            )
            opts_dict = {o[0]: f"{o[1]} — {o[2]}" for o in offerings}
            cost_dict = {o[0]: o[3] for o in offerings if len(o) > 3 and o[3] is not None}
            bare_metal_type = st.selectbox(
                t["deploy_bare_metal_select"],
                options=list(opts_dict.keys()),
                format_func=lambda x: opts_dict.get(x, x),
                key="deploy_ibm_bare_metal_type",
            )
            if bare_metal_type and bare_metal_type in cost_dict:
                num_nodes = st.number_input(
                    t["deploy_nodes_count"],
                    min_value=1,
                    max_value=100,
                    value=3,
                    help=t["deploy_nodes_count_help"],
                    key="deploy_ibm_nodes",
                )
                cost_per_hour = cost_dict[bare_metal_type]
                cost_per_node_day = cost_per_hour * 24
                cost_total_day = cost_per_node_day * num_nodes
                cost_total_month = cost_total_day * 30
                st.markdown(
                    f'<div class="deploy-cost-box">'
                    f'<div class="cost-label">{t["deploy_cost_per_node"]}</div>'
                    f'<div class="cost-value">${cost_per_node_day:.0f} / {t["deploy_day"]}</div>'
                    f'<div class="cost-total">{t["deploy_cost_total_day"]}: {t["deploy_cost_value"].format(cost=f"${cost_total_day:.0f}")}</div>'
                    f'<div class="cost-total">{t["deploy_cost_total_month"]}: {t["deploy_cost_value"].format(cost=f"${cost_total_month:.0f}")}</div>'
                    f'<div class="cost-label" style="margin-top:0.5rem; font-size:0.9rem;">{t["deploy_cost_note_ibm"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info(t["deploy_baremetal_note"])
        architecture_options = {"x86_64": t["deploy_arch_x86_64"], "aarch64": t["deploy_arch_aarch64"], "ppc64le": t["deploy_arch_ppc64le"]}
        architecture = st.selectbox(
            t["deploy_architecture"],
            options=list(architecture_options.keys()),
            format_func=lambda x: architecture_options[x],
            key="deploy_architecture_select",
        )


    ok_name, err_name = validate_cluster_name(cluster_name)
    ok_secret, err_secret = validate_pull_secret(pull_secret_content)
    if not ok_name:
        st.error(err_name)
    if not ok_secret:
        st.error(err_secret)

    if ok_name and ok_secret and pull_secret_content:
        install_config_yaml = build_install_config(
            platform=platform,
            cluster_name=cluster_name.strip(),
            base_domain=base_domain.strip(),
            pull_secret_content=pull_secret_content,
            ssh_public_key=ssh_key.strip() or None,
            aws_region=aws_region,
            azure_region=azure_region,
            azure_base_domain_resource_group=azure_resource_group,
            ibmcloud_region=ibm_region,
            architecture=architecture,
            control_plane_type=bare_metal_type,
            compute_type=bare_metal_type,
        )
        st.success(t["deploy_install_config_generated"])
        st.download_button(
            label="📥 " + t["deploy_download_install_config"],
            data=install_config_yaml,
            file_name="install-config.yaml",
            mime="text/yaml",
            key="deploy_dl_install_config",
        )
        run_script = build_run_script(
            platform=platform,
            cluster_name=cluster_name.strip(),
            install_dir="./cluster",
            aws_region=aws_region,
            azure_credentials_path=None,
            ibmcloud_region=ibm_region,
        )
        st.download_button(
            label="📥 " + t["deploy_download_run_script"],
            data=run_script,
            file_name="run-openshift-install.sh",
            mime="text/x-shellscript",
            key="deploy_dl_run_script",
        )
        if platform == "azure" and azure_subscription and azure_tenant and azure_client_id and azure_client_secret:
            azure_creds = build_azure_credentials_json(
                azure_subscription, azure_tenant, azure_client_id, azure_client_secret
            )
            st.download_button(
                label="📥 " + t["deploy_download_azure_creds"],
                data=azure_creds,
                file_name="osServicePrincipal.json",
                mime="application/json",
                key="deploy_dl_azure_creds",
            )
    else:
        st.info(t["deploy_need_pull_secret"])

    st.divider()
    st.subheader(t["deploy_destroy_title"])
    st.markdown(t["deploy_destroy_intro"])
    destroy_install_dir = st.text_input(
        t["deploy_install_dir"],
        value=st.session_state.get("deploy_destroy_install_dir", "./cluster"),
        help=t["deploy_install_dir_help"],
        key="deploy_destroy_install_dir_input",
    )
    st.session_state.deploy_destroy_install_dir = destroy_install_dir
    destroy_script = build_destroy_script(install_dir=destroy_install_dir.strip() or "./cluster")
    st.download_button(
        label="📥 " + t["deploy_download_destroy_script"],
        data=destroy_script,
        file_name="destroy-cluster.sh",
        mime="text/x-shellscript",
        key="deploy_dl_destroy_script",
    )
    st.stop()

# ---- Analysis page (default) ----
st.markdown(
    f"<h1><i class='fas fa-box-open' style='color:#007AFF; margin-right:0.35em;'></i>AlfsMigrationToolkit</h1>",
    unsafe_allow_html=True,
)
st.markdown(t["app_subtitle"])

# Import source: file or vCenter
import_options = ["file", "vcenter"] if VCENTER_AVAILABLE else ["file"]
import_source = st.radio(
    t["import_source"],
    options=import_options,
    format_func=lambda x: t["import_source_file"] if x == "file" else t["import_source_vcenter"],
    horizontal=True,
    key="import_source_radio",
)

sheets = None

if import_source == "file":
    uploaded = st.file_uploader(
        t["upload_label"],
        type=["xlsx", "xls", "csv"],
        help=t["upload_help"],
        key="file_uploader",
    )
    if not uploaded:
        st.info(t["upload_info"])
        st.stop()

    progress_bar = st.progress(0, text=t["import_progress"])
    try:
        progress_bar.progress(0.15, text=t["import_step_load"])
        sheets = load_rvtools_bytes(uploaded.getvalue(), uploaded.name or "export.csv")
        progress_bar.progress(0.5, text=t["import_step_analyze"])
    except Exception as e:
        progress_bar.empty()
        st.error(f"{t['error_load']}: {e}")
        st.stop()

else:
    # vCenter live import — centered card (form inside bordered container)
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        try:
            _vc_box = st.container(border=True)
        except TypeError:
            _vc_box = st.container()
        with _vc_box:
            st.markdown(
                "<div style='text-align:center;padding-bottom:0.75rem;border-bottom:1px solid #D1D1D6;margin-bottom:1rem;'>"
                "<h3 style='margin:0;font-size:1.35rem;'><i class='fas fa-server' style='color:#007AFF;'></i> "
                + t["import_source_vcenter"]
                + "</h3></div>",
                unsafe_allow_html=True,
            )
            with st.form("vcenter_login_form", clear_on_submit=False):
                vc_host = st.text_input(
                    t["vcenter_host"],
                    placeholder="vcenter.example.com",
                    help=t["vcenter_host_help"],
                    key="vcenter_host",
                )
                vc_user = st.text_input(t["vcenter_user"], key="vcenter_user", placeholder="administrator@vsphere.local")
                vc_password = st.text_input(
                    t["vcenter_password"],
                    type="password",
                    key="vcenter_password",
                )
                vc_skip_ssl = st.checkbox(
                    t["vcenter_skip_ssl"],
                    value=False,
                    help=t["vcenter_skip_ssl_help"],
                    key="vcenter_skip_ssl",
                )
                submitted = st.form_submit_button(t["import_connect"])

        if not submitted:
            st.info(t["upload_info"])
            st.stop()

    progress_bar = st.progress(0, text=t["import_progress"])
    try:
        progress_bar.progress(0.1, text=t["import_step_connect"])
        progress_bar.progress(0.3, text=t["import_step_fetch"])
        sheets = fetch_vms_from_vcenter(
            host=vc_host,
            user=vc_user,
            password=vc_password,
            skip_ssl=vc_skip_ssl,
        )
        progress_bar.progress(0.7, text=t["import_step_analyze"])
    except Exception as e:
        progress_bar.empty()
        st.error(f"{t.get('vcenter_error', 'vCenter error')}: {e}")
        st.stop()

progress_bar.progress(0.85, text=t["import_step_analyze"])

if not sheets:
    progress_bar.empty()
    st.warning(t["no_data"])
    st.stop()

vm_df = get_vm_data(sheets)
vm_df = filter_vms_for_migration(vm_df)

if vm_df.empty:
    progress_bar.empty()
    st.warning(t["no_vm_data"])
    st.stop()

# Cluster selection: build table with checkboxes
cluster_col = "cluster" if "cluster" in vm_df.columns else None
if cluster_col:
    vm_df["_cluster_norm"] = vm_df[cluster_col].fillna("").astype(str).str.strip()
    vm_df["_cluster_norm"] = vm_df["_cluster_norm"].replace("", "(unassigned)")
    cluster_counts = vm_df.groupby("_cluster_norm", dropna=False).agg(
        vms=("vm", "count"),
        vcpus=("cpus", "sum") if "cpus" in vm_df.columns else ("vm", "count"),
    ).reset_index()
    cluster_counts = cluster_counts.rename(columns={"_cluster_norm": "cluster"})
    cluster_counts["include"] = False
    cluster_df = cluster_counts[["cluster", "vms", "vcpus", "include"]].copy()
    cluster_df = cluster_df.rename(columns={
        "cluster": t["clusters_table_name"],
        "vms": t["clusters_table_vms"],
        "vcpus": t["clusters_table_vcpus"],
        "include": t["clusters_table_include"],
    })

    st.subheader(t["clusters_table_title"])
    st.caption(t["clusters_table_caption"])
    edited_clusters = st.data_editor(
        cluster_df,
        column_config={
            t["clusters_table_include"]: st.column_config.CheckboxColumn(
                t["clusters_table_include"],
                help=t["clusters_table_include_help"],
                default=False,
            ),
            t["clusters_table_name"]: st.column_config.TextColumn(t["clusters_table_name"], disabled=True),
            t["clusters_table_vms"]: st.column_config.NumberColumn(t["clusters_table_vms"], disabled=True),
            t["clusters_table_vcpus"]: st.column_config.NumberColumn(t["clusters_table_vcpus"], disabled=True),
        },
        hide_index=True,
        key="cluster_selector_editor",
    )
    selected_clusters = set(
        edited_clusters[edited_clusters[t["clusters_table_include"]]][t["clusters_table_name"]].tolist()
    )
    st.session_state.selected_clusters = selected_clusters
    vm_df = vm_df[vm_df["_cluster_norm"].isin(selected_clusters)].drop(columns=["_cluster_norm"], errors="ignore")
else:
    st.session_state.selected_clusters = None

if vm_df.empty:
    st.warning(t["clusters_none_selected"])
    st.stop()

progress_bar.progress(0.9, text=t["import_step_analyze"])
recommendations = analyze_all_vms(vm_df)
progress_bar.progress(1.0, text=t["import_step_done"])
progress_bar.empty()
stats = summary_stats(vm_df, recommendations)
stats["host_count"] = get_host_count(sheets) or get_host_count_from_vm_data(vm_df)
phases = build_migration_phases(recommendations, t)
plan_md = generate_plan_markdown(sheets, recommendations, stats, t)

# Persist for Cluster Design page
st.session_state.rvtools_stats = stats
st.session_state.rvtools_sheets = sheets
st.session_state.current_hosts = stats.get("host_count", st.session_state.current_hosts)

rec_df = pd.DataFrame([
    {
        t["rec_col_vm"]: r.vm_name,
        t["rec_col_status"]: r.status,
        t["rec_col_migration_type"]: r.migration_type,
        t["rec_col_effort"]: r.effort,
        t["rec_col_vcpus"]: r.cpus,
        t["rec_col_ram_mib"]: r.memory_mib,
        t["rec_col_disk_gb"]: r.provisioned_gb,
        t["rec_col_notes"]: "; ".join(r.issues) if r.issues else "–",
        t["rec_col_recommendations"]: "; ".join(r.recommendations[:3]) if r.recommendations else "–",
    }
    for r in recommendations
])

tab_overview, tab_recommendations, tab_plan, tab_export = st.tabs([
    "📊 " + t["tab_overview"],
    "✅ " + t["tab_recommendations"],
    "📋 " + t["tab_plan"],
    "💾 " + t["tab_export"],
])

with tab_overview:
    st.subheader(t["summary"])
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric(t["vms_migration"], stats["total_vms"])
    with c2:
        st.metric(t["ready"], stats["ready"], help=t["ready_help"])
    with c3:
        st.metric(t["review"], stats["review"], help=t["review_help"])
    with c4:
        st.metric(t["vcpus_total"], stats["total_vcpus"])
    with c5:
        st.metric(t["ram_gib"], stats["total_memory_gib"])
    st.metric(t["storage_provisioned_gb"], stats["total_storage_gb"])
    if stats["clusters"]:
        st.write("**" + t["clusters_source"] + ":**", ", ".join(stats["clusters"]))
    st.subheader(t["raw_data"])
    st.dataframe(vm_df.head(100), width="stretch")

with tab_recommendations:
    st.subheader(t["recommendations_per_vm"])
    st.dataframe(rec_df, width="stretch")

with tab_plan:
    st.subheader(t["migration_plan_phases"])
    for i, p in enumerate(phases):
        with st.expander(
            f"{p.name} – {len(p.vms)} " + t["vms"] + f" · {p.duration_estimate}",
            expanded=(i == 0),
        ):
            st.write(p.description)
            st.write("**" + t["prerequisites"] + "**")
            for pre in p.prerequisites:
                st.markdown(f"- {pre}")
            st.write("**" + t["risks"] + "**")
            for r in p.risks:
                st.markdown(f"- {r}")
            if p.vms:
                st.write("**" + t["vms"] + ":**")
                st.markdown("\n".join(f"- {v}" for v in p.vms[:30]) + ("\n- …" if len(p.vms) > 30 else ""))
    st.subheader(t["full_plan_md"])
    st.markdown(plan_md)

with tab_export:
    st.subheader(t["download_plan"])
    st.download_button(
        label="📥 " + t["download_plan_label"],
        data=plan_md,
        file_name="openshift-virt-migration-plan.md",
        mime="text/markdown",
    )
    st.subheader(t["download_csv"])
    rec_csv = rec_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 " + t["download_csv_label"],
        data=rec_csv,
        file_name="vm-recommendations.csv",
        mime="text/csv",
    )
