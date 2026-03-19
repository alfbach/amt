# -*- coding: utf-8 -*-
"""
Fetch available regions from cloud providers (AWS, Azure, IBM Cloud).
Uses boto3 for AWS; static lists for Azure and IBM Cloud.
"""

from typing import List, Tuple

# Azure regions (common OpenShift-supported locations)
AZURE_REGIONS = [
    ("eastus", "East US"),
    ("eastus2", "East US 2"),
    ("westus", "West US"),
    ("westus2", "West US 2"),
    ("westus3", "West US 3"),
    ("centralus", "Central US"),
    ("northcentralus", "North Central US"),
    ("southcentralus", "South Central US"),
    ("westcentralus", "West Central US"),
    ("canadacentral", "Canada Central"),
    ("brazilsouth", "Brazil South"),
    ("northeurope", "North Europe"),
    ("westeurope", "West Europe"),
    ("uksouth", "UK South"),
    ("ukwest", "UK West"),
    ("francecentral", "France Central"),
    ("germanywestcentral", "Germany West Central"),
    ("swedencentral", "Sweden Central"),
    ("norwayeast", "Norway East"),
    ("switzerlandnorth", "Switzerland North"),
    ("eastasia", "East Asia"),
    ("southeastasia", "Southeast Asia"),
    ("australiaeast", "Australia East"),
    ("australiasoutheast", "Australia Southeast"),
    ("japaneast", "Japan East"),
    ("japanwest", "Japan West"),
    ("koreacentral", "Korea Central"),
    ("southindia", "South India"),
    ("uaenorth", "UAE North"),
]

# IBM Cloud VPC regions
IBM_REGIONS = [
    ("us-south", "US South (Dallas)"),
    ("us-east", "US East (Washington DC)"),
    ("ca-tor", "Canada (Toronto)"),
    ("eu-de", "EU Germany (Frankfurt)"),
    ("eu-gb", "UK (London)"),
    ("jp-tok", "Japan (Tokyo)"),
    ("jp-osa", "Japan (Osaka)"),
    ("au-syd", "Australia (Sydney)"),
    ("br-sao", "Brazil (São Paulo)"),
]


def get_aws_regions() -> Tuple[List[Tuple[str, str]], None]:
    """
    Get AWS EC2 regions. Uses boto3 Session (no credentials needed).
    Returns list of (region_id, display_label).
    """
    try:
        from boto3.session import Session
        regions = Session().get_available_regions("ec2")
        if regions:
            # Sort, put us-east-1 first
            regions = sorted(regions)
            if "us-east-1" in regions:
                regions.remove("us-east-1")
                regions.insert(0, "us-east-1")
            return [(r, r) for r in regions], None
    except Exception:
        pass
    # Fallback static list
    fallback = [
        ("us-east-1", "us-east-1 (N. Virginia)"),
        ("us-east-2", "us-east-2 (Ohio)"),
        ("us-west-1", "us-west-1 (N. California)"),
        ("us-west-2", "us-west-2 (Oregon)"),
        ("eu-west-1", "eu-west-1 (Ireland)"),
        ("eu-west-2", "eu-west-2 (London)"),
        ("eu-central-1", "eu-central-1 (Frankfurt)"),
        ("eu-north-1", "eu-north-1 (Stockholm)"),
        ("ap-northeast-1", "ap-northeast-1 (Tokyo)"),
        ("ap-southeast-1", "ap-southeast-1 (Singapore)"),
        ("ap-southeast-2", "ap-southeast-2 (Sydney)"),
        ("sa-east-1", "sa-east-1 (São Paulo)"),
    ]
    return fallback, None


def get_azure_regions() -> List[Tuple[str, str]]:
    """Get Azure regions (static list)."""
    return AZURE_REGIONS


def get_ibm_regions() -> List[Tuple[str, str]]:
    """Get IBM Cloud regions (static list)."""
    return IBM_REGIONS


def get_regions(provider: str) -> List[Tuple[str, str]]:
    """
    Get available regions for the given cloud provider.
    Returns list of (region_id, display_label).
    """
    if provider == "aws":
        regions, _ = get_aws_regions()
        return regions
    if provider == "azure":
        return get_azure_regions()
    if provider == "ibmcloud":
        return get_ibm_regions()
    return []
