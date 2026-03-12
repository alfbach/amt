# -*- coding: utf-8 -*-
"""
Streamlit-App: RVTools-Analyse und Migrationsplan VMware → OpenShift Virtualization.
Mit Sprachwahl (EN/FR/DE), Konfiguration (Worker-Node, Overcommit) und Cluster-Design inkl. Einsparungen.
"""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import analyze_all_vms, summary_stats
from cluster_design import compute_cluster_design, compute_odf_design
from ha_network_diagram import build_topology_dot, get_ha_recommendations, get_network_settings
from i18n import get_translations
from migration_plan import build_migration_phases, generate_plan_markdown, generate_plan_with_risk_markdown
from risk_analysis import compute_risk_analysis
from rvtools_parser import filter_vms_for_migration, get_vm_data, get_host_count, load_rvtools
from deploy_prototype import (
    build_install_config,
    build_azure_credentials_json,
    build_run_script,
    build_destroy_script,
    validate_cluster_name,
    validate_pull_secret,
)

st.set_page_config(
    page_title="VMware → OpenShift Virt Migration",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Red Hat–inspired styling + Font Awesome (Red Hat brand icons)
st.markdown(
    "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'>",
    unsafe_allow_html=True,
)
st.markdown("""
<style>
    /* Red Hat brand: #EE0000 red, #151515 dark gray text */
    .rh-icon { color: #EE0000; margin-right: 0.35em; }
    .rh-icon.sidebar { color: #EE0000; font-size: 1.1rem; }
    :root {
        --rh-red: #EE0000;
        --rh-red-hover: #CC0000;
        --rh-dark: #151515;
        --rh-gray: #6E6E6E;
        --rh-bg: #FFFFFF;
        --rh-bg-secondary: #F5F5F5;
    }
    /* Main header / title area */
    h1 {
        color: var(--rh-dark) !important;
        font-weight: 600 !important;
        border-bottom: 3px solid var(--rh-red) !important;
        padding-bottom: 0.3em !important;
    }
    h2 {
        color: var(--rh-dark) !important;
        font-weight: 600 !important;
        border-left: 4px solid var(--rh-red) !important;
        padding-left: 0.4em !important;
    }
    h3 {
        color: var(--rh-dark) !important;
        font-weight: 600 !important;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%) !important;
    }
    [data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--rh-red) !important;
        opacity: 0.6;
    }
    /* Buttons use theme primaryColor; ensure contrast */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 500 !important;
    }
    /* Metric cards */
    [data-testid="stMetricValue"] {
        color: var(--rh-red) !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--rh-gray) !important;
        font-weight: 500 !important;
    }
    /* Expander */
    .streamlit-expanderHeader {
        background-color: var(--rh-bg-secondary) !important;
        border-left: 4px solid var(--rh-red) !important;
    }
    /* DataFrames */
    [data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0 !important;
        border-radius: 4px !important;
    }
    /* Success / info boxes */
    [data-testid="stAlert"] {
        border-left: 4px solid var(--rh-red) !important;
    }
    /* Links */
    a {
        color: var(--rh-red) !important;
        font-weight: 500 !important;
    }
    a:hover {
        color: var(--rh-red-hover) !important;
    }
    /* Number input focus */
    .stNumberInput input:focus {
        box-shadow: 0 0 0 2px var(--rh-red) !important;
        border-color: var(--rh-red) !important;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 2px solid var(--rh-red) !important;
        color: var(--rh-red) !important;
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

# Sidebar: Language & Navigation
with st.sidebar:
    st.markdown(
        "<p style='font-size:0.85rem; font-weight:700; margin-bottom:0.5rem;'>"
        "<i class='fab fa-redhat rh-icon sidebar'></i>Red Hat OpenShift</p>"
        "<p style='font-size:0.75rem; color:#c0c0c0; margin-top:0;'>"
        "<i class='fas fa-arrow-right' style='font-size:0.65rem; margin-right:0.25rem; color:#8a8a8a;'></i>VMware → OpenShift Virt</p>",
        unsafe_allow_html=True,
    )
    st.divider()
    lang_options = ["en", "de", "fr"]
    lang_labels = {"en": "English", "de": "Deutsch", "fr": "Français"}
    current = st.session_state.get("lang_select") or st.session_state.lang
    if current not in lang_options:
        current = "en"
    st.selectbox(
        "Language / Sprache / Langue",
        options=lang_options,
        format_func=lambda x: lang_labels[x],
        key="lang_select",
        index=lang_options.index(current),
    )
    st.session_state.lang = st.session_state.get("lang_select", st.session_state.lang)
    t = get_translations(st.session_state.lang)

    st.divider()
    # Navigation labels with icon hints (icons shown on each page title)
    page = st.radio(
        "Navigation",
        ["analysis", "config", "cluster_design", "ha_diagram", "migration_plan", "deploy"],
        format_func=lambda x: {
            "analysis": "Analysis",
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
        f"<h1><i class='fas fa-cog rh-icon'></i>{t['config_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["config_intro"])
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
        st.session_state.current_hosts = st.number_input(
            t["current_hosts"],
            min_value=0,
            max_value=500,
            value=st.session_state.current_hosts,
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
    st.session_state.odf_enabled = st.checkbox(
        t["odf_enable"],
        value=st.session_state.odf_enabled,
        help=t["odf_enable_help"],
    )
    if st.session_state.odf_enabled:
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
        with oc3:
            st.session_state.odf_growth_buffer_pct = st.number_input(
                t["odf_growth_buffer"],
                min_value=10,
                max_value=50,
                value=int(st.session_state.odf_growth_buffer_pct),
                step=5,
                help=t["odf_growth_buffer_help"],
            )
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

# ---- Cluster Design & Savings page ----
if st.session_state.page == "cluster_design":
    st.markdown(
        f"<h1><i class='fas fa-sitemap rh-icon'></i>{t['cluster_design_title']}</h1>",
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
        f"<h1><i class='fas fa-shield-halved rh-icon'></i>{t['ha_diagram_title']}</h1>",
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
    )
    st.subheader(t["ha_recommendations"])
    for rec in ha_recs:
        st.markdown("- " + rec)

    st.subheader(t["network_settings_table"])
    network_settings = get_network_settings()
    st.dataframe(
        pd.DataFrame(network_settings, columns=["Setting", "Recommended value"]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(t["topology_diagram"])
    dot = build_topology_dot(
        num_workers=workers_needed,
        worker_cores=st.session_state.worker_cores,
        worker_memory_gib=st.session_state.worker_memory_gib,
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
        f"<h1><i class='fas fa-clipboard-list rh-icon'></i>{t['migration_plan_title']}</h1>",
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
    phases = build_migration_phases(recommendations)
    global_risks, phase_risks, risk_summary = compute_risk_analysis(recommendations, phases, stats)

    st.subheader(t["migration_phases"])
    for p in phases:
        with st.expander(f"{p.name} — {len(p.vms)} " + t["vms"] + f" · {p.duration_estimate}", expanded=(p.name.startswith("Phase 1"))):
            st.write(p.description)
            st.markdown("**" + t["prerequisites"] + "**")
            for pre in p.prerequisites:
                st.markdown(f"- {pre}")
            st.markdown("**" + t["risks"] + "**")
            for r in p.risks:
                st.markdown(f"- {r}")
            if p.vms:
                st.markdown("**" + t["vms"] + ":**")
                st.code("\n".join(f"- {v}" for v in p.vms[:25] + (["…"] if len(p.vms) > 25 else [])))

    st.divider()
    st.subheader(t["risk_analysis_title"])
    overall = risk_summary.get("global_risk_level", "medium")
    st.metric(t["risk_overall"], overall.upper())
    st.caption(f"{t['risk_high']}: {risk_summary.get('high_risks', 0)} · {t['risk_medium']}: {risk_summary.get('medium_risks', 0)} · {t['risk_low']}: {risk_summary.get('low_risks', 0)}")

    st.markdown("**" + t["risk_global"] + "**")
    risk_df = pd.DataFrame([
        {"Category": r.category, "Level": r.level, "Description": r.description, "Mitigation": r.mitigation}
        for r in global_risks
    ])
    st.dataframe(risk_df, use_container_width=True, hide_index=True)

    st.markdown("**" + t["risk_per_phase"] + "**")
    for pr in phase_risks:
        st.markdown(f"- **{pr.phase_name}**: {pr.level} ({pr.vm_count} " + t["vms"] + ")")
        for r in pr.risks:
            st.caption(f"  {r.description} → {r.mitigation}")

    plan_with_risk_md = generate_plan_with_risk_markdown(
        sheets, recommendations, stats, global_risks, phase_risks, risk_summary
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
        f"<h1><i class='fas fa-cloud-arrow-up rh-icon'></i>{t['deploy_title']}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(t["deploy_intro"])
    st.warning(t["deploy_credentials_warning"])

    platform_options = ["aws", "azure", "ibmcloud", "baremetal"]
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
        f"<p style='font-size:1.1rem; color: var(--rh-gray, #6E6E6E); margin-top:-0.5rem; margin-bottom:1rem;'>"
        f"<i class='{platform_icons.get(platform, 'fas fa-cloud')}' style='color: var(--rh-red, #EE0000); margin-right:0.35em; font-size:1.25rem;'></i>"
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
        f"<h3><i class='{platform_icons.get(platform, 'fas fa-cloud')}' style='color: var(--rh-red); margin-right:0.25em;'></i>"
        f"{platform_labels.get(platform, platform)}</h3>",
        unsafe_allow_html=True,
    )
    aws_region = aws_access_key = aws_secret_key = None
    azure_region = azure_subscription = azure_tenant = azure_client_id = azure_client_secret = azure_resource_group = None
    ibm_region = ibm_api_key = None

    if platform == "aws":
        c1, c2 = st.columns(2)
        with c1:
            aws_region = st.text_input(t["deploy_aws_region"], value="us-east-1", key="deploy_aws_region")
            aws_access_key = st.text_input(t["deploy_aws_access_key"], type="password", key="deploy_aws_access_key")
        with c2:
            aws_secret_key = st.text_input(t["deploy_aws_secret_key"], type="password", key="deploy_aws_secret_key")
    elif platform == "azure":
        azure_region = st.text_input(t["deploy_azure_region"], value="eastus", key="deploy_azure_region")
        azure_resource_group = st.text_input(t["deploy_azure_resource_group"], value="os4-common", key="deploy_azure_rg")
        azure_subscription = st.text_input(t["deploy_azure_subscription"], type="password", key="deploy_azure_sub")
        azure_tenant = st.text_input(t["deploy_azure_tenant"], type="password", key="deploy_azure_tenant")
        azure_client_id = st.text_input(t["deploy_azure_client_id"], type="password", key="deploy_azure_cid")
        azure_client_secret = st.text_input(t["deploy_azure_client_secret"], type="password", key="deploy_azure_secret")
    elif platform == "ibmcloud":
        c1, c2 = st.columns(2)
        with c1:
            ibm_region = st.text_input(t["deploy_ibm_region"], value="us-south", key="deploy_ibm_region")
        with c2:
            ibm_api_key = st.text_input(t["deploy_ibm_api_key"], type="password", key="deploy_ibm_apikey")
    else:
        st.info(t["deploy_baremetal_note"])

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
    f"<h1><i class='fab fa-redhat rh-icon'></i>{t['app_title']}</h1>",
    unsafe_allow_html=True,
)
st.markdown(t["app_subtitle"])

uploaded = st.file_uploader(
    t["upload_label"],
    type=["xlsx", "xls", "csv"],
    help=t["upload_help"],
)

if not uploaded:
    st.info(t["upload_info"])
    st.stop()

with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
    tmp.write(uploaded.getvalue())
    tmp_path = tmp.name

try:
    sheets = load_rvtools(tmp_path)
except Exception as e:
    st.error(f"{t['error_load']}: {e}")
    st.stop()
finally:
    Path(tmp_path).unlink(missing_ok=True)

if not sheets:
    st.warning(t["no_data"])
    st.stop()

vm_df = get_vm_data(sheets)
vm_df = filter_vms_for_migration(vm_df)

if vm_df.empty:
    st.warning(t["no_vm_data"])
    st.stop()

recommendations = analyze_all_vms(vm_df)
stats = summary_stats(vm_df, recommendations)
phases = build_migration_phases(recommendations)
plan_md = generate_plan_markdown(sheets, recommendations, stats)

# Persist for Cluster Design page
st.session_state.rvtools_stats = stats
st.session_state.rvtools_sheets = sheets

rec_df = pd.DataFrame([
    {
        "VM": r.vm_name,
        "Status": r.status,
        "Migrationstyp": r.migration_type,
        "Aufwand": r.effort,
        "vCPUs": r.cpus,
        "RAM (MiB)": r.memory_mib,
        "Disk (GB)": r.provisioned_gb,
        "Hinweise": "; ".join(r.issues) if r.issues else "–",
        "Empfehlungen": "; ".join(r.recommendations[:3]) if r.recommendations else "–",
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
    st.dataframe(vm_df.head(100), use_container_width=True)

with tab_recommendations:
    st.subheader(t["recommendations_per_vm"])
    st.dataframe(rec_df, use_container_width=True)

with tab_plan:
    st.subheader(t["migration_plan_phases"])
    for p in phases:
        with st.expander(f"{p.name} – {len(p.vms)} " + t["vms"] + f" · {p.duration_estimate}", expanded=(p.name.startswith("Phase 1"))):
            st.write(p.description)
            st.write("**" + t["prerequisites"] + "**")
            for pre in p.prerequisites:
                st.markdown(f"- {pre}")
            st.write("**" + t["risks"] + "**")
            for r in p.risks:
                st.markdown(f"- {r}")
            if p.vms:
                st.write("**" + t["vms"] + ":**")
                st.code("\n".join(f"- {v}" for v in p.vms[:30] + (["…"] if len(p.vms) > 30 else [])))
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
