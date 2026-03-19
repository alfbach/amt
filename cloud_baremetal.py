# -*- coding: utf-8 -*-
"""
Fetch bare metal instance/offering options from cloud providers (AWS, IBM Cloud, Azure).
Uses boto3 for AWS when available; falls back to static lists otherwise.
"""

from typing import List, Optional, Tuple

# Static bare metal instance types (fallback when API unavailable)
# (id, label, description, cost_per_hour_usd) - cost approximate for us-east-1 on-demand
AWS_METAL_TYPES_STATIC = [
    ("m5.metal", "m5.metal", "48 vCPU, 192 GiB", 4.61),
    ("m5d.metal", "m5d.metal", "48 vCPU, 192 GiB, NVMe", 5.42),
    ("m5n.metal", "m5n.metal", "48 vCPU, 192 GiB", 5.42),
    ("m5zn.metal", "m5zn.metal", "48 vCPU, 192 GiB", 5.42),
    ("m6i.metal", "m6i.metal", "64 vCPU, 256 GiB", 6.14),
    ("m6id.metal", "m6id.metal", "64 vCPU, 256 GiB, NVMe", 7.22),
    ("c5.metal", "c5.metal", "96 vCPU, 192 GiB", 4.08),
    ("c5d.metal", "c5d.metal", "96 vCPU, 192 GiB, NVMe", 4.80),
    ("c6i.metal", "c6i.metal", "64 vCPU, 128 GiB", 4.08),
    ("r5.metal", "r5.metal", "96 vCPU, 768 GiB", 6.05),
    ("r5d.metal", "r5d.metal", "96 vCPU, 768 GiB, NVMe", 7.11),
    ("i3.metal", "i3.metal", "72 vCPU, 512 GiB, NVMe", 4.99),
    ("i4i.metal", "i4i.metal", "128 vCPU, 1024 GiB, NVMe", 10.67),
]

IBM_BARE_METAL_STATIC = [
    ("bx2d-metal-192x768", "bx2d-metal-192x768", "192 vCPU, 768 GiB", 28.80),
    ("bx2d-metal-96x384", "bx2d-metal-96x384", "96 vCPU, 384 GiB", 14.40),
    ("bx2d-metal-48x192", "bx2d-metal-48x192", "48 vCPU, 192 GiB", 7.20),
]

AZURE_BARE_METAL_STATIC = [
    ("Standard_HB120rs_v2", "Standard_HB120rs_v2", "HBv2, 120 cores", 12.96),
    ("Standard_HB96rs_v2", "Standard_HB96rs_v2", "HBv2, 96 cores", 10.37),
    ("SAP_HANA", "SAP HANA Large Instance", "SAP HANA dedicated", None),
]


# Approximate hourly cost (USD) for API-fetched AWS metal types (us-east-1 on-demand)
AWS_METAL_COST_LOOKUP = {t[0]: t[3] for t in AWS_METAL_TYPES_STATIC}


def fetch_aws_metal_instance_types(
    region: str = "us-east-1",
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> Tuple[List[Tuple[str, str, str]], Optional[str]]:
    """
    Fetch EC2 bare metal instance types from AWS via boto3.
    Returns list of (id, label, description), and error message if any.
    Falls back to static list if boto3 unavailable or credentials missing.
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        return AWS_METAL_TYPES_STATIC, None

    if not access_key or not secret_key:
        return AWS_METAL_TYPES_STATIC, None

    try:
        client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=access_key.strip(),
            aws_secret_access_key=secret_key.strip(),
        )
        paginator = client.get_paginator("describe_instance_types")
        result = []
        for page in paginator.paginate():
            for it in page.get("InstanceTypes", []):
                name = it.get("InstanceType", "")
                if "metal" in name.lower():
                    vcpus = it.get("VCpuInfo", {}).get("DefaultVCpus", 0)
                    mem = it.get("MemoryInfo", {}).get("SizeInMiB", 0)
                    mem_gib = mem // 1024 if mem else 0
                    desc = f"{vcpus} vCPU, {mem_gib} GiB"
                    cost = AWS_METAL_COST_LOOKUP.get(name)
                    result.append((name, name, desc, cost))
        if result:
            result.sort(key=lambda x: x[0])
            return result, None
    except (ClientError, NoCredentialsError) as e:
        return AWS_METAL_TYPES_STATIC, str(e)
    except Exception as e:
        return AWS_METAL_TYPES_STATIC, str(e)
    return AWS_METAL_TYPES_STATIC, None


def fetch_ibm_bare_metal_offerings(
    _region: Optional[str] = None,
    _api_key: Optional[str] = None,
) -> Tuple[List[Tuple[str, str, str]], Optional[str]]:
    """
    IBM Cloud bare metal server offerings. Static list (VPC API requires ibm-vpc SDK).
    """
    return IBM_BARE_METAL_STATIC, None


def fetch_azure_bare_metal_offerings(
    region: Optional[str] = None,
    credentials: Optional[dict] = None,
) -> Tuple[List[Tuple[str, str, str]], Optional[str]]:
    """
    Azure bare metal (HANA Large Instance, HBv2, etc.) - static list.
    Azure's general bare metal API is not straightforward; use static offerings.
    """
    return AZURE_BARE_METAL_STATIC, None


def get_bare_metal_offerings(
    provider: str,
    region: Optional[str] = None,
    aws_access_key: Optional[str] = None,
    aws_secret_key: Optional[str] = None,
    ibm_api_key: Optional[str] = None,
) -> Tuple[List[Tuple[str, str, str]], Optional[str]]:
    """
    Get bare metal offerings for the given cloud provider.
    Returns (list of (id, label, description), error_message).
    """
    if provider == "aws":
        return fetch_aws_metal_instance_types(
            region=region or "us-east-1",
            access_key=aws_access_key,
            secret_key=aws_secret_key,
        )
    if provider == "ibmcloud":
        return fetch_ibm_bare_metal_offerings()
    if provider == "azure":
        return fetch_azure_bare_metal_offerings(region=region)
    return [], None
