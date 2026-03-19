# -*- coding: utf-8 -*-
"""
Generate install-config.yaml and run scripts for OpenShift prototype deployment
via openshift-install (AWS, Azure, IBM Cloud, Bare metal).
Credentials are not stored in install-config for AWS (use env vars); for Azure
we generate osServicePrincipal.json; for IBM Cloud we document API key usage.
"""

from typing import Optional, Tuple


def _escape_pull_secret(secret: str) -> str:
    """Ensure pull secret is a single-line string suitable for YAML (single-quoted)."""
    s = secret.replace("\n", " ").replace("\r", " ").strip()
    return s.replace("'", "''")  # YAML single-quote escape


def build_install_config(
    platform: str,
    cluster_name: str,
    base_domain: str,
    pull_secret_content: str,
    ssh_public_key: Optional[str] = None,
    # AWS
    aws_region: Optional[str] = None,
    # Azure
    azure_region: Optional[str] = None,
    azure_base_domain_resource_group: Optional[str] = None,
    # IBM Cloud
    ibmcloud_region: Optional[str] = None,
    # Bare metal (on-prem)
    architecture: Optional[str] = None,
    # Cloud bare metal instance type (AWS/IBM/Azure)
    control_plane_type: Optional[str] = None,
    compute_type: Optional[str] = None,
) -> str:
    """
    Build install-config.yaml content as a string.
    platform: 'aws' | 'azure' | 'ibmcloud' | 'baremetal'
    pull_secret_content: raw JSON string from Red Hat pull secret.
    """
    lines = [
        "apiVersion: v1",
        "baseDomain: " + base_domain,
        "metadata:",
        "  name: " + cluster_name,
        "pullSecret: '" + _escape_pull_secret(pull_secret_content) + "'",
    ]
    if ssh_public_key and ssh_public_key.strip():
        lines.append("sshKey: |")
        for k in ssh_public_key.strip().split("\n"):
            lines.append("  " + k)
    lines.append("platform:")
    if platform == "aws":
        region = aws_region or "us-east-1"
        lines.append("  aws:")
        lines.append("    region: " + region)
    elif platform == "azure":
        region = azure_region or "eastus"
        lines.append("  azure:")
        lines.append("    baseDomainResourceGroupName: " + (azure_base_domain_resource_group or "os4-common"))
        lines.append("    cloudName: AzurePublicCloud")
        lines.append("    region: " + region)
    elif platform == "ibmcloud":
        region = ibmcloud_region or "us-south"
        lines.append("  ibmcloud:")
        lines.append("    region: " + region)
    else:
        # baremetal / none
        lines.append("  none: {}")
    if platform == "baremetal" and architecture:
        lines.append("# Target architecture (use matching openshift-install binary): " + architecture)
    # Cloud bare metal: controlPlane and compute instance types
    instance_type = control_plane_type or compute_type
    if platform == "aws" and instance_type:
        lines.append("controlPlane:")
        lines.append("  platform:")
        lines.append("    aws:")
        lines.append("      type: " + instance_type)
        lines.append("compute:")
        lines.append("- name: worker")
        lines.append("  platform:")
        lines.append("    aws:")
        lines.append("      type: " + (compute_type or instance_type))
        lines.append("  replicas: 3")
    elif platform == "ibmcloud" and instance_type:
        lines.append("controlPlane:")
        lines.append("  platform:")
        lines.append("    ibmcloud:")
        lines.append("      type: " + instance_type)
        lines.append("compute:")
        lines.append("- name: worker")
        lines.append("  platform:")
        lines.append("    ibmcloud:")
        lines.append("      type: " + (compute_type or instance_type))
        lines.append("  replicas: 3")
    elif platform == "azure" and instance_type:
        lines.append("controlPlane:")
        lines.append("  platform:")
        lines.append("    azure:")
        lines.append("      type: " + instance_type)
        lines.append("compute:")
        lines.append("- name: worker")
        lines.append("  platform:")
        lines.append("    azure:")
        lines.append("      type: " + (compute_type or instance_type))
        lines.append("  replicas: 3")
    lines.append("networking:")
    lines.append("  networkType: OVNKubernetes")
    lines.append("  machineNetwork:")
    lines.append("  - cidr: 10.0.0.0/16")
    return "\n".join(lines)


def build_azure_credentials_json(
    subscription_id: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Build osServicePrincipal.json content for Azure (non-interactive install)."""
    import json
    return json.dumps({
        "subscriptionId": subscription_id.strip(),
        "tenantId": tenant_id.strip(),
        "clientId": client_id.strip(),
        "clientSecret": client_secret.strip(),
    }, indent=2)


def build_run_script(
    platform: str,
    cluster_name: str,
    install_dir: str = "./cluster",
    aws_region: Optional[str] = None,
    azure_credentials_path: Optional[str] = None,
    ibmcloud_region: Optional[str] = None,
) -> str:
    """
    Build a shell script that documents env vars and runs openshift-install.
    Credentials are NOT embedded; use placeholders so the script is safe to store.
    """
    lines = [
        "#!/usr/bin/env bash",
        "# OpenShift prototype cluster deployment (generated). Do not commit with real credentials.",
        "set -e",
        "",
        "INSTALL_DIR=\"" + install_dir.replace('"', '\\"') + "\"",
        "mkdir -p \"$INSTALL_DIR\"",
        "",
    ]
    if platform == "aws":
        lines.append("# Set AWS credentials (env vars) before running:")
        lines.append("export AWS_ACCESS_KEY_ID=\"<your-access-key-id>\"")
        lines.append("export AWS_SECRET_ACCESS_KEY=\"<your-secret-access-key>\"")
        lines.append("export AWS_REGION=\"" + (aws_region or "us-east-1").replace('"', '\\"') + "\"")
        lines.append("")
    elif platform == "azure":
        lines.append("# Azure: copy osServicePrincipal.json to ~/.azure/ or set AZURE_AUTH_LOCATION")
        lines.append("mkdir -p ~/.azure")
        if azure_credentials_path:
            lines.append("cp \"" + azure_credentials_path.replace('"', '\\"') + "\" ~/.azure/osServicePrincipal.json")
        else:
            lines.append("# cp /path/to/osServicePrincipal.json ~/.azure/osServicePrincipal.json")
        lines.append("")
    elif platform == "ibmcloud":
        lines.append("# Set IBM Cloud API key (env var) before running:")
        lines.append("export IBMCLOUD_API_KEY=\"<your-ibmcloud-api-key>\"")
        if ibmcloud_region:
            lines.append("export IBMCLOUD_REGION=\"" + ibmcloud_region.replace('"', '\\"') + "\"")
        lines.append("")
    lines.append("# Copy install-config.yaml into $INSTALL_DIR, then run:")
    lines.append("openshift-install create cluster --dir=\"$INSTALL_DIR\" --log-level=info")
    lines.append("# Or create install-config only: openshift-install create install-config --dir=\"$INSTALL_DIR\"")
    return "\n".join(lines)


def build_destroy_script(install_dir: str = "./cluster", log_level: str = "info") -> str:
    """
    Build a shell script that runs openshift-install destroy cluster.
    Uses the same install directory that was used for create cluster (must contain metadata).
    """
    safe_dir = install_dir.replace('"', '\\"')
    lines = [
        "#!/usr/bin/env bash",
        "# Destroy OpenShift cluster (openshift-install destroy cluster).",
        "# Ensure the install dir contains the metadata from the cluster you want to destroy.",
        "set -e",
        "",
        "INSTALL_DIR=\"" + safe_dir + "\"",
        "if [[ ! -d \"$INSTALL_DIR\" ]]; then",
        "  echo \"Error: Install directory $INSTALL_DIR not found.\" >&2",
        "  exit 1",
        "fi",
        "",
        "# Optional: set cloud credentials if destroy needs them (e.g. AWS_ACCESS_KEY_ID, etc.)",
        "echo \"Destroying cluster (install dir: $INSTALL_DIR)...\"",
        "openshift-install destroy cluster --dir=\"$INSTALL_DIR\" --log-level=" + log_level,
        "echo \"Done.\"",
    ]
    return "\n".join(lines)


def validate_cluster_name(name: str) -> Tuple[bool, str]:
    """Cluster name: lowercase, hyphens, periods only."""
    if not name or not name.strip():
        return False, "Cluster name is required"
    s = name.strip()
    for c in s:
        if c not in "abcdefghijklmnopqrstuvwxyz0123456789-.":
            return False, "Only lowercase letters, numbers, hyphens and periods allowed"
    return True, ""


def validate_pull_secret(content: str) -> Tuple[bool, str]:
    """Basic check that pull secret looks like JSON with auths."""
    if not content or not content.strip():
        return False, "Pull secret is required"
    stripped = content.strip()
    if "auths" not in stripped and '"auths"' not in stripped:
        return False, "Pull secret should be JSON from Red Hat (contain 'auths')"
    return True, ""
