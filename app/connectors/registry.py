"""
Regulatory Source and Connector Registry (Phases 66–69).

Manages official regulatory sources and registered connector implementations
for SEBI, RBI, IRDAI, PFRDA, and IFSCA.
"""

import logging
from typing import Dict, List, Optional, Any, Type
from pydantic import BaseModel, Field

from app.connectors.authority import RegulatoryAuthority, get_authority_metadata
from app.connectors.base import RegulatoryConnector

logger = logging.getLogger("regintel.connectors.registry")


class RegulatorySource(BaseModel):
    """Configuration model for an official regulatory source/endpoint."""
    source_id: str
    authority: RegulatoryAuthority
    source_type: str = "Listing"  # "Listing", "Archive", "CuratedDocument", "SearchPage"
    name: str
    base_url: str
    listing_url: str
    enabled: bool = True
    crawl_frequency: str = "daily"  # "hourly", "daily", "weekly"
    parser: str = "default"
    document_types: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    priority: int = 1
    max_pages: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Official Regulatory Source Definitions for Indian Regulators
OFFICIAL_SOURCES: List[RegulatorySource] = [
    # -------------------------------------------------------------
    # 1. SEBI Sources
    # -------------------------------------------------------------
    RegulatorySource(
        source_id="sebi_circulars",
        authority=RegulatoryAuthority.SEBI,
        source_type="Listing",
        name="SEBI Circulars",
        base_url="https://www.sebi.gov.in",
        listing_url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0",
        enabled=True,
        document_types=["Circular"],
        category="General",
        priority=1,
        max_pages=3
    ),
    RegulatorySource(
        source_id="sebi_master_circulars",
        authority=RegulatoryAuthority.SEBI,
        source_type="Listing",
        name="SEBI Master Circulars",
        base_url="https://www.sebi.gov.in",
        listing_url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=1",
        enabled=True,
        document_types=["Master Circular"],
        category="General",
        priority=1,
        max_pages=2
    ),
    RegulatorySource(
        source_id="sebi_regulations",
        authority=RegulatoryAuthority.SEBI,
        source_type="Listing",
        name="SEBI Regulations",
        base_url="https://www.sebi.gov.in",
        listing_url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=1&smid=0",
        enabled=True,
        document_types=["Regulation"],
        category="General",
        priority=2,
        max_pages=2
    ),

    # -------------------------------------------------------------
    # 2. RBI Sources (Phase 66)
    # -------------------------------------------------------------
    RegulatorySource(
        source_id="rbi_notifications",
        authority=RegulatoryAuthority.RBI,
        source_type="Listing",
        name="RBI Notifications",
        base_url="https://www.rbi.org.in",
        listing_url="https://www.rbi.org.in/Scripts/NotificationUser.aspx",
        enabled=True,
        document_types=["Notification", "Circular"],
        category="Banking & Monetary",
        priority=1,
        max_pages=3
    ),
    RegulatorySource(
        source_id="rbi_master_directions",
        authority=RegulatoryAuthority.RBI,
        source_type="Listing",
        name="RBI Master Directions",
        base_url="https://www.rbi.org.in",
        listing_url="https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx",
        enabled=True,
        document_types=["Master Direction"],
        category="Banking Regulation",
        priority=1,
        max_pages=2
    ),
    RegulatorySource(
        source_id="rbi_master_circulars",
        authority=RegulatoryAuthority.RBI,
        source_type="Listing",
        name="RBI Master Circulars",
        base_url="https://www.rbi.org.in",
        listing_url="https://www.rbi.org.in/Scripts/BS_ViewMasterCirculardetails.aspx",
        enabled=True,
        document_types=["Master Circular"],
        category="Banking Regulation",
        priority=1,
        max_pages=2
    ),
    RegulatorySource(
        source_id="rbi_press_releases",
        authority=RegulatoryAuthority.RBI,
        source_type="Listing",
        name="RBI Press Releases",
        base_url="https://www.rbi.org.in",
        listing_url="https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
        enabled=False,
        document_types=["Press Release"],
        category="General",
        priority=3,
        max_pages=1
    ),

    # -------------------------------------------------------------
    # 3. IRDAI Sources (Phase 67)
    # -------------------------------------------------------------
    RegulatorySource(
        source_id="irdai_circulars",
        authority=RegulatoryAuthority.IRDAI,
        source_type="Listing",
        name="IRDAI Circulars",
        base_url="https://irdai.gov.in",
        listing_url="https://irdai.gov.in/circulars",
        enabled=True,
        document_types=["Circular"],
        category="Insurance",
        priority=1,
        max_pages=3
    ),
    RegulatorySource(
        source_id="irdai_master_circulars",
        authority=RegulatoryAuthority.IRDAI,
        source_type="Listing",
        name="IRDAI Master Circulars",
        base_url="https://irdai.gov.in",
        listing_url="https://irdai.gov.in/master-circulars",
        enabled=True,
        document_types=["Master Circular"],
        category="Insurance",
        priority=1,
        max_pages=2
    ),
    RegulatorySource(
        source_id="irdai_regulations",
        authority=RegulatoryAuthority.IRDAI,
        source_type="Listing",
        name="IRDAI Regulations",
        base_url="https://irdai.gov.in",
        listing_url="https://irdai.gov.in/regulations",
        enabled=True,
        document_types=["Regulation"],
        category="Insurance",
        priority=2,
        max_pages=2
    ),

    # -------------------------------------------------------------
    # 4. PFRDA Sources (Phase 68)
    # -------------------------------------------------------------
    RegulatorySource(
        source_id="pfrda_circulars",
        authority=RegulatoryAuthority.PFRDA,
        source_type="Listing",
        name="PFRDA Circulars",
        base_url="https://www.pfrda.org.in",
        listing_url="https://www.pfrda.org.in/index1.cshtml?lsid=82",
        enabled=True,
        document_types=["Circular"],
        category="Pension",
        priority=1,
        max_pages=3
    ),
    RegulatorySource(
        source_id="pfrda_guidelines",
        authority=RegulatoryAuthority.PFRDA,
        source_type="Listing",
        name="PFRDA Guidelines & Master Circulars",
        base_url="https://www.pfrda.org.in",
        listing_url="https://www.pfrda.org.in/index1.cshtml?lsid=83",
        enabled=True,
        document_types=["Guideline", "Master Circular"],
        category="Pension",
        priority=1,
        max_pages=2
    ),
    RegulatorySource(
        source_id="pfrda_regulations",
        authority=RegulatoryAuthority.PFRDA,
        source_type="Listing",
        name="PFRDA Regulations",
        base_url="https://www.pfrda.org.in",
        listing_url="https://www.pfrda.org.in/index1.cshtml?lsid=84",
        enabled=True,
        document_types=["Regulation"],
        category="Pension",
        priority=2,
        max_pages=2
    ),

    # -------------------------------------------------------------
    # 5. IFSCA Sources (Phase 69)
    # -------------------------------------------------------------
    RegulatorySource(
        source_id="ifsca_circulars",
        authority=RegulatoryAuthority.IFSCA,
        source_type="Listing",
        name="IFSCA Circulars",
        base_url="https://ifsca.gov.in",
        listing_url="https://ifsca.gov.in/Circular",
        enabled=True,
        document_types=["Circular"],
        category="International Finance",
        priority=1,
        max_pages=3
    ),
    RegulatorySource(
        source_id="ifsca_regulations",
        authority=RegulatoryAuthority.IFSCA,
        source_type="Listing",
        name="IFSCA Regulations",
        base_url="https://ifsca.gov.in",
        listing_url="https://ifsca.gov.in/Regulation",
        enabled=True,
        document_types=["Regulation"],
        category="International Finance",
        priority=2,
        max_pages=2
    ),
    RegulatorySource(
        source_id="ifsca_frameworks",
        authority=RegulatoryAuthority.IFSCA,
        source_type="Listing",
        name="IFSCA Frameworks & Guidelines",
        base_url="https://ifsca.gov.in",
        listing_url="https://ifsca.gov.in/Framework",
        enabled=True,
        document_types=["Framework", "Guideline"],
        category="International Finance",
        priority=2,
        max_pages=2
    )
]


class SourceRegistry:
    """Central registry providing lookup and management for regulatory sources."""

    def __init__(self, initial_sources: Optional[List[RegulatorySource]] = None):
        self._sources: Dict[str, RegulatorySource] = {}
        for s in (initial_sources or OFFICIAL_SOURCES):
            self.register_source(s)

    def register_source(self, source: RegulatorySource):
        """Registers a regulatory source."""
        self._sources[source.source_id] = source

    def get_source(self, source_id: str) -> Optional[RegulatorySource]:
        """Looks up a source by source_id."""
        return self._sources.get(source_id)

    def get_sources(
        self,
        authority: Optional[RegulatoryAuthority | str] = None,
        enabled_only: bool = True
    ) -> List[RegulatorySource]:
        """Returns sources filtered by authority and enabled status."""
        target_auth = None
        if authority:
            if isinstance(authority, RegulatoryAuthority):
                target_auth = authority
            elif isinstance(authority, str):
                try:
                    target_auth = RegulatoryAuthority(authority.strip().upper())
                except ValueError:
                    target_auth = None

        results = list(self._sources.values())
        if target_auth:
            results = [s for s in results if s.authority == target_auth]
        if enabled_only:
            results = [s for s in results if s.enabled]
        return results


class ConnectorRegistry:
    """
    Singleton registry managing connector instances across all regulatory authorities.
    Allows dynamic lookup, iteration, and decoupled integration.
    """

    _instance: Optional["ConnectorRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConnectorRegistry, cls).__new__(cls)
            cls._instance._connectors = {}
        return cls._instance

    def register(self, connector: RegulatoryConnector):
        """Registers a connector instance for its authority."""
        self._connectors[connector.authority] = connector
        logger.info(f"Registered connector for authority: {connector.authority.value}")

    def get_connector(
        self,
        authority: RegulatoryAuthority | str
    ) -> Optional[RegulatoryConnector]:
        """Retrieves connector for a given authority enum or string."""
        target_auth = None
        if isinstance(authority, RegulatoryAuthority):
            target_auth = authority
        elif isinstance(authority, str):
            try:
                target_auth = RegulatoryAuthority(authority.strip().upper())
            except ValueError:
                return None

        return self._connectors.get(target_auth)

    def list_connectors(self) -> List[RegulatoryConnector]:
        """Returns all registered connectors."""
        return list(self._connectors.values())


# Global singletons
source_registry = SourceRegistry()
connector_registry = ConnectorRegistry()
