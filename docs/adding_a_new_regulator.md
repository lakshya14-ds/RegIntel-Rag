# Developer Guide: Adding a New Regulator to RegIntel

RegIntel uses an extensible, generic regulatory connector architecture designed to make adding a 6th regulator (e.g., Telecom Regulatory Authority of India — **TRAI**, Competition Commission of India — **CCI**, or Insolvency and Bankruptcy Board of India — **IBBI**) seamless and modular, requiring **zero modifications to shared downstream intelligence engines**.

---

## 7-Step Extension Workflow

```
       1. Authority Enum & Metadata
                   ↓
     2. Connector Class (BaseRegulatoryConnector)
                   ↓
           3. Register Sources
                   ↓
    4. Deterministic Metadata & Ref Parsing
                   ↓
        5. Mocked Test Fixtures
                   ↓
      6. Connector Contract Suite Test
                   ↓
            7. Enable Ingestion
```

---

### Step 1: Add Authority to `RegulatoryAuthority` Enum & Metadata

File: `app/connectors/authority.py`

1. Add the authority key to `RegulatoryAuthority`:
   ```python
   class RegulatoryAuthority(str, Enum):
       SEBI = "SEBI"
       RBI = "RBI"
       IRDAI = "IRDAI"
       PFRDA = "PFRDA"
       IFSCA = "IFSCA"
       NEWREG = "NEWREG"  # e.g., TRAI or CCI
   ```
2. Define the authority metadata in `AUTHORITY_REGISTRY`:
   ```python
   AUTHORITY_REGISTRY[RegulatoryAuthority.NEWREG] = AuthorityMetadata(
       authority=RegulatoryAuthority.NEWREG,
       full_name="New Regulatory Authority of India",
       official_website="https://newreg.gov.in",
       allowed_domains=["newreg.gov.in"],
       primary_legislation="New Regulatory Authority Act, 2000",
       reference_number_standard="NEWREG/... or F.No. ...",
       default_categories=["Telecommunications", "Licensing", "Tariffs"],
       document_types=["Regulation", "Circular", "Order", "Direction"]
   )
   ```

---

### Step 2: Implement Connector Class Extending `BaseRegulatoryConnector`

File: `app/connectors/newreg.py`

Subclass `BaseRegulatoryConnector` and define:
```python
from app.connectors.authority import RegulatoryAuthority
from app.connectors.base import BaseRegulatoryConnector, CrawlResult
from app.connectors.registry import RegulatorySource, source_registry, connector_registry
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentMetadata

class NewRegConnector(BaseRegulatoryConnector):
    """Production-grade connector for NEWREG."""

    @property
    def authority(self) -> RegulatoryAuthority:
        return RegulatoryAuthority.NEWREG

    @property
    def allowed_domains(self) -> List[str]:
        return ["newreg.gov.in"]

    async def discover_sources(self) -> List[RegulatorySource]:
        return source_registry.get_sources_for_authority(self.authority)

    async def discover_documents(self, source: Optional[RegulatorySource] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        # Implement dynamic listing/archive page scraping with incremental deduplication
        ...

    async def fetch_document(self, url: str) -> CrawlResult:
        # Uses httpx and pypdf with polite rate-limiting, error handling, and content validation
        ...

    def extract_metadata(self, text: str, title: Optional[str] = None, url: Optional[str] = None) -> DocumentMetadata:
        # Deterministic extraction of reference numbers, departments, dates, and relationships
        ...
```

---

### Step 3: Register Official Sources in `SourceRegistry`

File: `app/connectors/registry.py`

Add authoritative sources to `OFFICIAL_REGULATORY_SOURCES`:
```python
RegulatorySource(
    source_id="newreg_circulars",
    authority=RegulatoryAuthority.NEWREG,
    source_type="Listing",
    name="NEWREG Circulars & Directives",
    base_url="https://newreg.gov.in",
    listing_url="https://newreg.gov.in/circulars",
    enabled=True,
    document_types=["Circular", "Directive"],
    category="Licensing",
    priority=1,
    max_pages=3
),
```

Auto-register the connector in `app/connectors/__init__.py`:
```python
from app.connectors.newreg import NewRegConnector
connector_registry.register(NewRegConnector())
```

---

### Step 4: Implement Deterministic Metadata & Reference Parsing

In `app/connectors/newreg.py`:
- **Reference Regex**: Compile patterns matching official gazette / circular reference numbers.
- **Department Taxonomy**: List official directorates or wings.
- **Relationship Detection**: Detect phrases like `in supersession of`, `amends regulation`, or `in continuation to`.
- **Dates**: Extract publication date and effective date clauses (`with effect from <date>`).

---

### Step 5: Add Mocked Test Fixtures

Create test suite: `tests/unit/test_newreg_connector.py`
- Mocked listing page discovery
- Canonical URL handling and deduplication
- Reference number extraction
- Normalization into `RegulatoryDocument`
- Handling missing metadata (never fabricate metadata)
- HTTP failure and timeout handling
- Content hash update detection

---

### Step 6: Run Reusable Connector Contract Suite

File: `tests/unit/test_connector_contract.py`

Add `RegulatoryAuthority.NEWREG` to the parameterized authorities:
```python
@pytest.mark.parametrize("authority_key", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA", "NEWREG"])
def test_connector_registration(authority_key):
    ...
```
Verify:
1. Registration & domain whitelisting
2. Source discovery
3. Document discovery
4. Deterministic metadata extraction contract
5. Canonical normalization contract

---

### Step 7: Enable Ingestion & Verify Downstream Reuse

The new regulator automatically integrates with:
- **`IngestionPipeline`**: Content hashing, chunk hashing, embedding reuse, and incremental updates.
- **`TimelineService`**: Version history and supersession graphs.
- **`RequirementExtractor` & `ObligationExtractor`**: Deontic extraction, compliance checklist creation.
- **`DateExtractor` & `DeadlineEngine`**: Effective-date calculation and recurring deadline tracking.
- **`AuthorityFilter` & Hybrid Retrieval**: Multi-authority search filtering across vector and BM25.
- **`ConnectorRunTracker`**: Health and observability dashboards.
