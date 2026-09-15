"""
Unified Regulatory Authority Model (Phase 66).

Defines supported Indian financial regulators:
- SEBI (Securities and Exchange Board of India)
- RBI (Reserve Bank of India)
- IRDAI (Insurance Regulatory and Development Authority of India)
- PFRDA (Pension Fund Regulatory and Development Authority)
- IFSCA (International Financial Services Centres Authority)
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RegulatoryAuthority(str, Enum):
    """Enumeration of officially supported financial regulatory authorities."""
    SEBI = "SEBI"
    RBI = "RBI"
    IRDAI = "IRDAI"
    PFRDA = "PFRDA"
    IFSCA = "IFSCA"


class AuthorityMetadata(BaseModel):
    """Metadata describing a regulatory authority, its mandate, and official domain."""
    code: RegulatoryAuthority
    name: str
    short_name: str
    country: str = "IN"
    domain: str
    official_domain: str
    description: str
    enabled: bool = True
    default_document_types: List[str] = Field(default_factory=list)


# Authoritative Registry of Regulatory Authorities in India
AUTHORITY_REGISTRY: Dict[RegulatoryAuthority, AuthorityMetadata] = {
    RegulatoryAuthority.SEBI: AuthorityMetadata(
        code=RegulatoryAuthority.SEBI,
        name="Securities and Exchange Board of India",
        short_name="SEBI",
        country="IN",
        domain="sebi.gov.in",
        official_domain="https://www.sebi.gov.in",
        description="Statutory regulator for securities and commodity markets in India.",
        enabled=True,
        default_document_types=["Circular", "Master Circular", "Regulation", "Order", "Notification", "Advisory", "Consultation Paper"]
    ),
    RegulatoryAuthority.RBI: AuthorityMetadata(
        code=RegulatoryAuthority.RBI,
        name="Reserve Bank of India",
        short_name="RBI",
        country="IN",
        domain="rbi.org.in",
        official_domain="https://www.rbi.org.in",
        description="Central bank and primary banking & financial systems regulator of India.",
        enabled=True,
        default_document_types=["Notification", "Circular", "Master Circular", "Master Direction", "Press Release", "Guideline", "Order", "FAQ"]
    ),
    RegulatoryAuthority.IRDAI: AuthorityMetadata(
        code=RegulatoryAuthority.IRDAI,
        name="Insurance Regulatory and Development Authority of India",
        short_name="IRDAI",
        country="IN",
        domain="irdai.gov.in",
        official_domain="https://irdai.gov.in",
        description="Autonomous statutory body regulating and developing the insurance industry in India.",
        enabled=True,
        default_document_types=["Circular", "Master Circular", "Regulation", "Notification", "Order", "Guideline", "Exposure Draft", "Press Release"]
    ),
    RegulatoryAuthority.PFRDA: AuthorityMetadata(
        code=RegulatoryAuthority.PFRDA,
        name="Pension Fund Regulatory and Development Authority",
        short_name="PFRDA",
        country="IN",
        domain="pfrda.org.in",
        official_domain="https://www.pfrda.org.in",
        description="Statutory regulatory body overseeing and regulating the pension sector in India.",
        enabled=True,
        default_document_types=["Circular", "Notification", "Guideline", "Regulation", "Master Circular", "Order", "Press Release", "Report"]
    ),
    RegulatoryAuthority.IFSCA: AuthorityMetadata(
        code=RegulatoryAuthority.IFSCA,
        name="International Financial Services Centres Authority",
        short_name="IFSCA",
        country="IN",
        domain="ifsca.gov.in",
        official_domain="https://ifsca.gov.in",
        description="Unified statutory regulatory authority for international financial services centres in India (GIFT City).",
        enabled=True,
        default_document_types=["Regulation", "Circular", "Direction", "Notification", "Guideline", "Framework", "Order", "Consultation Paper"]
    ),
}


def get_authority_metadata(authority: RegulatoryAuthority | str) -> Optional[AuthorityMetadata]:
    """Retrieves authoritative metadata for a given authority code or string."""
    if isinstance(authority, RegulatoryAuthority):
        return AUTHORITY_REGISTRY.get(authority)
    if not authority or not isinstance(authority, str):
        return None
    try:
        enum_val = RegulatoryAuthority(authority.strip().upper())
        return AUTHORITY_REGISTRY.get(enum_val)
    except ValueError:
        return None


def list_authorities(enabled_only: bool = True) -> List[AuthorityMetadata]:
    """Returns all registered authorities, optionally filtered to enabled only."""
    authorities = list(AUTHORITY_REGISTRY.values())
    if enabled_only:
        return [a for a in authorities if a.enabled]
    return authorities
