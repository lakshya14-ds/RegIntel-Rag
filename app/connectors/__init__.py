"""
Regulatory Connectors Package (Phases 66–69).

Exports:
- RegulatoryAuthority enum and metadata models
- RegulatoryConnector, BaseRegulatoryConnector contracts
- RegulatorySource and SourceRegistry
- ConnectorRegistry singleton with registered SEBI, RBI, IRDAI, PFRDA, IFSCA connectors
- ConnectorRun, ConnectorHealth, ConnectorRunTracker
"""

from app.connectors.authority import (
    RegulatoryAuthority,
    AuthorityMetadata,
    AUTHORITY_REGISTRY,
    get_authority_metadata,
    list_authorities
)
from app.connectors.base import (
    CrawlResult,
    RegulatoryConnector,
    BaseRegulatoryConnector
)
from app.connectors.registry import (
    RegulatorySource,
    SourceRegistry,
    ConnectorRegistry,
    source_registry,
    connector_registry
)
from app.connectors.health import (
    ConnectorRun,
    ConnectorHealth,
    ConnectorRunTracker,
    connector_tracker
)

# Import connector modules to trigger registration with connector_registry
import app.connectors.sebi
import app.connectors.rbi
import app.connectors.irdai
import app.connectors.pfrda
import app.connectors.ifsca

__all__ = [
    "RegulatoryAuthority",
    "AuthorityMetadata",
    "AUTHORITY_REGISTRY",
    "get_authority_metadata",
    "list_authorities",
    "CrawlResult",
    "RegulatoryConnector",
    "BaseRegulatoryConnector",
    "RegulatorySource",
    "SourceRegistry",
    "ConnectorRegistry",
    "source_registry",
    "connector_registry",
    "ConnectorRun",
    "ConnectorHealth",
    "ConnectorRunTracker",
    "connector_tracker"
]
