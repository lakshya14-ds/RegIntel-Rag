"""
Persistence Repository for Compliance Intelligence (Phases 61, 62, 63).

Supports:
- Saving and querying RegulatoryRequirement objects
- Saving and querying RegulatoryObligation objects
- Saving, querying, and updating ComplianceChecklist objects
- Dual-mode persistence: MongoDB Atlas with graceful local JSON fallback
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import settings
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.temporal_models import RegulatoryDateEvent
from app.compliance.alert_models import (
    RegulatoryEvent,
    RegulatoryDeadline,
    RegulatoryAlert,
    Watchlist,
)
from app.compliance.overlap_models import RegulatoryOverlap
from app.compliance.conflict_models import RegulatoryConflict, ConflictReviewEvent

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class ComplianceRepository:
    """
    Manages database and filesystem persistence for requirements, obligations, checklists,
    date events, regulatory events, deadlines, alerts, and watchlists.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_data_dir = data_dir or (settings.processed_data_dir / "compliance")
        self.req_dir = self.base_data_dir / "requirements"
        self.ob_dir = self.base_data_dir / "obligations"
        self.chk_dir = self.base_data_dir / "checklists"
        self.date_events_dir = self.base_data_dir / "date_events"
        self.events_dir = self.base_data_dir / "events"
        self.deadlines_dir = self.base_data_dir / "deadlines"
        self.alerts_dir = self.base_data_dir / "alerts"
        self.watchlists_dir = self.base_data_dir / "watchlists"
        self.overlaps_dir = self.base_data_dir / "overlaps"
        self.conflicts_dir = self.base_data_dir / "conflicts"

        # Ensure local fallback storage directories exist
        self.req_dir.mkdir(parents=True, exist_ok=True)
        self.ob_dir.mkdir(parents=True, exist_ok=True)
        self.chk_dir.mkdir(parents=True, exist_ok=True)
        self.date_events_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.deadlines_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.watchlists_dir.mkdir(parents=True, exist_ok=True)
        self.overlaps_dir.mkdir(parents=True, exist_ok=True)
        self.conflicts_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # REQUIREMENTS PERSISTENCE (Phase 61)
    # -------------------------------------------------------------------------

    def save_requirements(self, requirements: List[RegulatoryRequirement]) -> int:
        """Upserts a list of requirements to MongoDB and local JSON storage."""
        if not requirements:
            return 0

        count = 0
        # 1. Local filesystem persistence (guaranteed fallback)
        for req in requirements:
            try:
                fp = self.req_dir / f"{req.requirement_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(req.model_dump(), f, indent=2, ensure_ascii=False)
                count += 1
            except Exception as e:
                logger.warning(f"Error saving requirement {req.requirement_id} locally: {e}")

        # 2. MongoDB persistence if available
        try:
            from app.db import get_requirements_collection
            coll = get_requirements_collection()
            for req in requirements:
                data = req.model_dump()
                coll.update_one(
                    {"requirement_id": req.requirement_id},
                    {"$set": data},
                    upsert=True
                )
        except Exception as e:
            logger.debug(f"MongoDB save_requirements bypassed/failed: {e}")

        return count

    def get_requirement_by_id(self, requirement_id: str) -> Optional[RegulatoryRequirement]:
        """Retrieves a single requirement by its unique ID."""
        clean_id = requirement_id.strip()

        # Try MongoDB first
        try:
            from app.db import get_requirements_collection
            coll = get_requirements_collection()
            doc = coll.find_one({"requirement_id": clean_id})
            if doc:
                doc.pop("_id", None)
                return RegulatoryRequirement.model_validate(doc)
        except Exception:
            pass

        # Try local filesystem
        fp = self.req_dir / f"{clean_id}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return RegulatoryRequirement.model_validate(json.load(f))
            except Exception as e:
                logger.error(f"Failed to read local requirement file {fp}: {e}")

        return None

    def get_requirements(
        self,
        document_id: Optional[str] = None,
        section_id: Optional[str] = None,
        authority: Optional[str] = None,
        document_type: Optional[str] = None,
        requirement_type: Optional[str] = None,
        confidence: Optional[str] = None,
        effective_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RegulatoryRequirement]:
        """Queries requirements with multiple optional filters and pagination."""
        # 1. Try MongoDB
        try:
            from app.db import get_requirements_collection
            coll = get_requirements_collection()
            query: Dict[str, Any] = {}
            if document_id:
                query["document_id"] = document_id
            if section_id:
                query["section_id"] = section_id
            if authority:
                query["authority"] = authority
            if document_type:
                query["document_type"] = document_type
            if requirement_type:
                query["requirement_type"] = requirement_type
            if confidence:
                query["confidence"] = confidence
            if effective_date:
                query["effective_date"] = effective_date

            cursor = coll.find(query).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryRequirement.model_validate(doc))
            if results or coll.count_documents({}) > 0:
                return results
        except Exception:
            pass

        # 2. Local fallback
        all_reqs: List[RegulatoryRequirement] = []
        for fp in self.req_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    req = RegulatoryRequirement.model_validate(json.load(f))
                    if document_id and req.document_id != document_id:
                        continue
                    if section_id and req.section_id != section_id:
                        continue
                    if authority and req.authority.lower() != authority.lower():
                        continue
                    if document_type and req.document_type != document_type:
                        continue
                    if requirement_type and req.requirement_type != requirement_type:
                        continue
                    if confidence and req.confidence != confidence:
                        continue
                    if effective_date and req.effective_date != effective_date:
                        continue
                    all_reqs.append(req)
            except Exception:
                continue

        return all_reqs[offset: offset + limit]

    # -------------------------------------------------------------------------
    # OBLIGATIONS PERSISTENCE (Phase 62)
    # -------------------------------------------------------------------------

    def save_obligations(self, obligations: List[RegulatoryObligation]) -> int:
        """Upserts a list of obligations to MongoDB and local JSON storage."""
        if not obligations:
            return 0

        count = 0
        for ob in obligations:
            try:
                fp = self.ob_dir / f"{ob.obligation_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(ob.model_dump(), f, indent=2, ensure_ascii=False)
                count += 1
            except Exception as e:
                logger.warning(f"Error saving obligation {ob.obligation_id} locally: {e}")

        try:
            from app.db import get_obligations_collection
            coll = get_obligations_collection()
            for ob in obligations:
                data = ob.model_dump()
                coll.update_one(
                    {"obligation_id": ob.obligation_id},
                    {"$set": data},
                    upsert=True
                )
        except Exception as e:
            logger.debug(f"MongoDB save_obligations bypassed/failed: {e}")

        return count

    def get_obligation_by_id(self, obligation_id: str) -> Optional[RegulatoryObligation]:
        """Retrieves a single obligation by its unique ID."""
        clean_id = obligation_id.strip()

        try:
            from app.db import get_obligations_collection
            coll = get_obligations_collection()
            doc = coll.find_one({"obligation_id": clean_id})
            if doc:
                doc.pop("_id", None)
                return RegulatoryObligation.model_validate(doc)
        except Exception:
            pass

        fp = self.ob_dir / f"{clean_id}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return RegulatoryObligation.model_validate(json.load(f))
            except Exception as e:
                logger.error(f"Failed to read local obligation file {fp}: {e}")

        return None

    def get_obligations(
        self,
        document_id: Optional[str] = None,
        requirement_id: Optional[str] = None,
        authority: Optional[str] = None,
        obligated_party: Optional[str] = None,
        obligation_type: Optional[str] = None,
        status: Optional[str] = None,
        confidence: Optional[str] = None,
        effective_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RegulatoryObligation]:
        """Queries obligations with optional filters and pagination."""
        try:
            from app.db import get_obligations_collection
            coll = get_obligations_collection()
            query: Dict[str, Any] = {}
            if document_id:
                query["document_id"] = document_id
            if requirement_id:
                query["requirement_id"] = requirement_id
            if authority:
                query["authority"] = authority
            if obligated_party:
                query["obligated_party"] = {"$regex": obligated_party, "$options": "i"}
            if obligation_type:
                query["obligation_type"] = obligation_type
            if status:
                query["status"] = status
            if confidence:
                query["confidence"] = confidence
            if effective_date:
                query["effective_date"] = effective_date

            cursor = coll.find(query).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryObligation.model_validate(doc))
            if results or coll.count_documents({}) > 0:
                return results
        except Exception:
            pass

        all_obs: List[RegulatoryObligation] = []
        for fp in self.ob_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    ob = RegulatoryObligation.model_validate(json.load(f))
                    if document_id and ob.document_id != document_id:
                        continue
                    if requirement_id and ob.requirement_id != requirement_id:
                        continue
                    if authority and ob.authority != authority:
                        continue
                    if obligated_party and (not ob.obligated_party or obligated_party.lower() not in ob.obligated_party.lower()):
                        continue
                    if obligation_type and ob.obligation_type != obligation_type:
                        continue
                    if status and ob.status != status:
                        continue
                    if confidence and ob.confidence != confidence:
                        continue
                    if effective_date and ob.effective_date != effective_date:
                        continue
                    all_obs.append(ob)
            except Exception:
                continue

        return all_obs[offset: offset + limit]

    # -------------------------------------------------------------------------
    # COMPLIANCE CHECKLISTS PERSISTENCE (Phase 63)
    # -------------------------------------------------------------------------

    def save_checklist(self, checklist: ComplianceChecklist) -> bool:
        """Upserts a compliance checklist."""
        checklist.recalculate_metrics()

        # Local storage
        try:
            fp = self.chk_dir / f"{checklist.checklist_id}.json"
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(checklist.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save checklist {checklist.checklist_id} locally: {e}")
            return False

        # MongoDB storage
        try:
            from app.db import get_checklists_collection
            coll = get_checklists_collection()
            data = checklist.model_dump()
            coll.update_one(
                {"checklist_id": checklist.checklist_id},
                {"$set": data},
                upsert=True
            )
        except Exception as e:
            logger.debug(f"MongoDB save_checklist bypassed/failed: {e}")

        return True

    def get_checklist_by_id(self, checklist_id: str) -> Optional[ComplianceChecklist]:
        """Retrieves a compliance checklist by ID."""
        clean_id = checklist_id.strip()

        try:
            from app.db import get_checklists_collection
            coll = get_checklists_collection()
            doc = coll.find_one({"checklist_id": clean_id})
            if doc:
                doc.pop("_id", None)
                chk = ComplianceChecklist.model_validate(doc)
                chk.recalculate_metrics()
                return chk
        except Exception:
            pass

        fp = self.chk_dir / f"{clean_id}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    chk = ComplianceChecklist.model_validate(json.load(f))
                    chk.recalculate_metrics()
                    return chk
            except Exception as e:
                logger.error(f"Failed to read local checklist {fp}: {e}")

        return None

    def get_checklists(
        self,
        authority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ComplianceChecklist]:
        """Lists saved compliance checklists with optional authority filtering."""
        query = {}
        if authority:
            query["authority"] = authority

        try:
            from app.db import get_checklists_collection
            coll = get_checklists_collection()
            cursor = coll.find(query).sort("updated_at", -1).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                chk = ComplianceChecklist.model_validate(doc)
                chk.recalculate_metrics()
                results.append(chk)
            if results or coll.count_documents({}) > 0:
                return results
        except Exception:
            pass

        all_chks = []
        for fp in self.chk_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    chk = ComplianceChecklist.model_validate(json.load(f))
                    chk.recalculate_metrics()
                    if authority and chk.authority != authority:
                        continue
                    all_chks.append(chk)
            except Exception:
                continue

        all_chks.sort(key=lambda x: x.updated_at, reverse=True)
        return all_chks[offset: offset + limit]

    def update_checklist_item_status(
        self,
        checklist_id: str,
        item_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[ComplianceChecklist]:
        """Updates a specific checklist item's review status or notes without losing other items."""
        chk = self.get_checklist_by_id(checklist_id)
        if not chk:
            return None

        updated = False
        from datetime import datetime
        now_iso = datetime.utcnow().isoformat()

        for item in chk.items:
            if item.item_id == item_id:
                if status:
                    item.status = status  # type: ignore
                if notes is not None:
                    item.notes = notes
                item.updated_at = now_iso
                updated = True
                break

        if updated:
            chk.updated_at = now_iso
            chk.recalculate_metrics()
            self.save_checklist(chk)
            return chk

        return None

    # -------------------------------------------------------------------------
    # REGULATORY DATE EVENTS PERSISTENCE (Phase 64)
    # -------------------------------------------------------------------------

    def save_date_events(self, events: List[RegulatoryDateEvent]) -> int:
        """Upserts regulatory date events to MongoDB and local filesystem."""
        if not events:
            return 0

        count = 0
        for ev in events:
            try:
                fp = self.date_events_dir / f"{ev.event_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(ev.model_dump(), f, indent=2, ensure_ascii=False)
                count += 1
            except Exception as e:
                logger.warning(f"Error saving date event {ev.event_id} locally: {e}")

        try:
            from app.db import get_date_events_collection
            coll = get_date_events_collection()
            for ev in events:
                data = ev.model_dump()
                coll.update_one(
                    {"event_id": ev.event_id},
                    {"$set": data},
                    upsert=True
                )
        except Exception as e:
            logger.debug(f"MongoDB save_date_events bypassed/failed: {e}")

        return count

    def get_date_events(
        self,
        document_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RegulatoryDateEvent]:
        """Queries stored regulatory date events with optional filters."""
        query: Dict[str, Any] = {}
        if document_id:
            query["document_id"] = document_id.strip()
        if event_type:
            query["event_type"] = event_type.strip().upper()

        try:
            from app.db import get_date_events_collection
            coll = get_date_events_collection()
            cursor = coll.find(query).sort("date", 1).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryDateEvent.model_validate(doc))
            if results or coll.count_documents(query) > 0:
                return results
        except Exception:
            pass

        events = []
        for fp in self.date_events_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if document_id and data.get("document_id") != document_id.strip():
                        continue
                    if event_type and data.get("event_type") != event_type.strip().upper():
                        continue
                    events.append(RegulatoryDateEvent.model_validate(data))
            except Exception:
                continue

        events.sort(key=lambda x: x.date or "9999-99-99")
        return events[offset: offset + limit]

    def get_calendar_date_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[RegulatoryDateEvent]:
        """Returns chronological date events within a date window for calendar views."""
        all_events = self.get_date_events(event_type=event_type, limit=500)
        filtered = []
        for ev in all_events:
            if not ev.date:
                continue
            if start_date and ev.date < start_date:
                continue
            if end_date and ev.date > end_date:
                continue
            filtered.append(ev)
        filtered.sort(key=lambda x: x.date or "")
        return filtered

    def get_upcoming_date_events(
        self,
        days: int = 30,
        as_of_date: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[RegulatoryDateEvent]:
        """Returns regulatory changes becoming effective/due in the next N days (64.15)."""
        from datetime import datetime, timedelta
        ref_str = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")
        try:
            ref_dt = datetime.strptime(ref_str, "%Y-%m-%d")
            end_dt = ref_dt + timedelta(days=days)
            end_str = end_dt.strftime("%Y-%m-%d")
        except Exception:
            return []

        all_events = self.get_date_events(event_type=event_type, limit=500)
        upcoming = [
            ev for ev in all_events
            if ev.date and ref_str <= ev.date <= end_str
        ]
        upcoming.sort(key=lambda x: x.date or "")
        return upcoming

    # -------------------------------------------------------------------------
    # REGULATORY DEADLINES PERSISTENCE (Phase 65)
    # -------------------------------------------------------------------------

    def save_deadlines(self, deadlines: List[RegulatoryDeadline]) -> int:
        """Upserts regulatory deadlines to MongoDB and local filesystem."""
        if not deadlines:
            return 0

        count = 0
        for ddl in deadlines:
            try:
                fp = self.deadlines_dir / f"{ddl.deadline_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(ddl.model_dump(), f, indent=2, ensure_ascii=False)
                count += 1
            except Exception as e:
                logger.warning(f"Error saving deadline {ddl.deadline_id} locally: {e}")

        try:
            from app.db import get_deadlines_collection
            coll = get_deadlines_collection()
            for ddl in deadlines:
                coll.update_one(
                    {"deadline_id": ddl.deadline_id},
                    {"$set": ddl.model_dump()},
                    upsert=True
                )
        except Exception as e:
            logger.debug(f"MongoDB save_deadlines bypassed/failed: {e}")

        return count

    def get_deadlines(
        self,
        document_id: Optional[str] = None,
        obligation_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RegulatoryDeadline]:
        """Queries stored regulatory deadlines."""
        query: Dict[str, Any] = {}
        if document_id:
            query["document_id"] = document_id.strip()
        if obligation_id:
            query["obligation_id"] = obligation_id.strip()
        if status:
            query["status"] = status.strip().upper()

        try:
            from app.db import get_deadlines_collection
            coll = get_deadlines_collection()
            cursor = coll.find(query).sort("due_date", 1).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryDeadline.model_validate(doc))
            if results or coll.count_documents(query) > 0:
                return results
        except Exception:
            pass

        deadlines = []
        for fp in self.deadlines_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if document_id and data.get("document_id") != document_id.strip():
                        continue
                    if obligation_id and data.get("obligation_id") != obligation_id.strip():
                        continue
                    if status and data.get("status") != status.strip().upper():
                        continue
                    deadlines.append(RegulatoryDeadline.model_validate(data))
            except Exception:
                continue

        deadlines.sort(key=lambda x: x.due_date or "9999-99-99")
        return deadlines[offset: offset + limit]

    # -------------------------------------------------------------------------
    # REGULATORY ALERTS PERSISTENCE & DEDUPLICATION (Phase 65)
    # -------------------------------------------------------------------------

    def save_alerts(self, alerts: List[RegulatoryAlert]) -> int:
        """
        Saves alerts while enforcing deduplication on dedup_hash (65.10).
        If an alert with identical dedup_hash exists, it is not duplicated.
        """
        if not alerts:
            return 0

        # Load existing dedup hashes
        existing_hashes = set()
        for fp in self.alerts_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if d.get("dedup_hash"):
                        existing_hashes.add(d["dedup_hash"])
            except Exception:
                continue

        saved_count = 0
        to_persist = []
        for alt in alerts:
            if alt.dedup_hash in existing_hashes:
                continue
            existing_hashes.add(alt.dedup_hash)
            to_persist.append(alt)

            try:
                fp = self.alerts_dir / f"{alt.alert_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(alt.model_dump(), f, indent=2, ensure_ascii=False)
                saved_count += 1
            except Exception as e:
                logger.warning(f"Error saving alert {alt.alert_id} locally: {e}")

        if to_persist:
            try:
                from app.db import get_alerts_collection
                coll = get_alerts_collection()
                for alt in to_persist:
                    coll.update_one(
                        {"dedup_hash": alt.dedup_hash},
                        {"$setOnInsert": alt.model_dump()},
                        upsert=True
                    )
            except Exception as e:
                logger.debug(f"MongoDB save_alerts bypassed/failed: {e}")

        return saved_count

    def get_alerts(
        self,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        status: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[RegulatoryAlert]:
        """Queries stored alerts with filtering and pagination."""
        query: Dict[str, Any] = {}
        if severity:
            query["severity"] = severity.strip().upper()
        if alert_type:
            query["alert_type"] = alert_type.strip().upper()
        if status:
            query["status"] = status.strip().upper()
        if document_id:
            query["document_id"] = document_id.strip()

        try:
            from app.db import get_alerts_collection
            coll = get_alerts_collection()
            cursor = coll.find(query).sort("created_at", -1).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryAlert.model_validate(doc))
            if results or coll.count_documents(query) > 0:
                return results
        except Exception:
            pass

        alerts = []
        for fp in self.alerts_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if severity and data.get("severity") != severity.strip().upper():
                        continue
                    if alert_type and data.get("alert_type") != alert_type.strip().upper():
                        continue
                    if status and data.get("status") != status.strip().upper():
                        continue
                    if document_id and data.get("document_id") != document_id.strip():
                        continue
                    alerts.append(RegulatoryAlert.model_validate(data))
            except Exception:
                continue

        alerts.sort(key=lambda x: x.created_at, reverse=True)
        return alerts[offset: offset + limit]

    def get_alert_by_id(self, alert_id: str) -> Optional[RegulatoryAlert]:
        """Retrieves a single alert by ID."""
        try:
            from app.db import get_alerts_collection
            coll = get_alerts_collection()
            doc = coll.find_one({"alert_id": alert_id.strip()})
            if doc:
                doc.pop("_id", None)
                return RegulatoryAlert.model_validate(doc)
        except Exception:
            pass

        fp = self.alerts_dir / f"{alert_id.strip()}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return RegulatoryAlert.model_validate(json.load(f))
            except Exception:
                pass
        return None

    def update_alert_status(self, alert_id: str, new_status: str) -> Optional[RegulatoryAlert]:
        """Updates alert status (e.g. READ, DISMISSED)."""
        alt = self.get_alert_by_id(alert_id)
        if not alt:
            return None

        alt.status = new_status.upper()  # type: ignore
        now_iso = datetime.utcnow().isoformat()
        if new_status.upper() == "READ":
            alt.read_at = now_iso
        elif new_status.upper() == "DISMISSED":
            alt.dismissed_at = now_iso

        # Save update
        try:
            fp = self.alerts_dir / f"{alt.alert_id}.json"
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(alt.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        try:
            from app.db import get_alerts_collection
            coll = get_alerts_collection()
            coll.update_one(
                {"alert_id": alt.alert_id},
                {"$set": {"status": alt.status, "read_at": alt.read_at, "dismissed_at": alt.dismissed_at}}
            )
        except Exception:
            pass

        return alt

    # -------------------------------------------------------------------------
    # WATCHLISTS PERSISTENCE (Phase 65.9)
    # -------------------------------------------------------------------------

    def save_watchlist(self, watchlist: Watchlist) -> Watchlist:
        """Saves or updates a user watchlist."""
        try:
            fp = self.watchlists_dir / f"{watchlist.watchlist_id}.json"
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(watchlist.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Error saving watchlist {watchlist.watchlist_id} locally: {e}")

        try:
            from app.db import get_watchlists_collection
            coll = get_watchlists_collection()
            coll.update_one(
                {"watchlist_id": watchlist.watchlist_id},
                {"$set": watchlist.model_dump()},
                upsert=True
            )
        except Exception as e:
            logger.debug(f"MongoDB save_watchlist bypassed/failed: {e}")

        return watchlist

    def get_watchlists(self, user_id: Optional[str] = None) -> List[Watchlist]:
        """Returns all watchlists, optionally filtered by user_id."""
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id.strip()

        try:
            from app.db import get_watchlists_collection
            coll = get_watchlists_collection()
            cursor = coll.find(query).sort("created_at", -1)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(Watchlist.model_validate(doc))
            if results or coll.count_documents(query) > 0:
                return results
        except Exception:
            pass

        watchlists = []
        for fp in self.watchlists_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if user_id and data.get("user_id") != user_id.strip():
                        continue
                    watchlists.append(Watchlist.model_validate(data))
            except Exception:
                continue

        return watchlists

    def get_watchlist_by_id(self, watchlist_id: str) -> Optional[Watchlist]:
        """Retrieves a watchlist by ID."""
        try:
            from app.db import get_watchlists_collection
            coll = get_watchlists_collection()
            doc = coll.find_one({"watchlist_id": watchlist_id.strip()})
            if doc:
                doc.pop("_id", None)
                return Watchlist.model_validate(doc)
        except Exception:
            pass

        fp = self.watchlists_dir / f"{watchlist_id.strip()}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return Watchlist.model_validate(json.load(f))
            except Exception:
                pass
        return None

    # -------------------------------------------------------------------------
    # REGULATORY OVERLAPS PERSISTENCE (Phase 73)
    # -------------------------------------------------------------------------

    def save_overlaps(self, overlaps: List[RegulatoryOverlap]) -> int:
        """Upserts regulatory overlaps to MongoDB Atlas and local filesystem."""
        if not overlaps:
            return 0

        count = 0
        for ovl in overlaps:
            try:
                fp = self.overlaps_dir / f"{ovl.overlap_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(ovl.model_dump(), f, indent=2, ensure_ascii=False)
                count += 1
            except Exception as e:
                logger.warning(f"Error saving overlap {ovl.overlap_id} locally: {e}")

        try:
            from app.db import get_overlaps_collection
            coll = get_overlaps_collection()
            for ovl in overlaps:
                coll.update_one(
                    {"overlap_id": ovl.overlap_id},
                    {"$set": ovl.model_dump()},
                    upsert=True
                )
        except Exception as e:
            logger.debug(f"MongoDB save_overlaps bypassed/failed: {e}")

        return count

    def get_overlap_by_id(self, overlap_id: str) -> Optional[RegulatoryOverlap]:
        """Retrieves a single regulatory overlap by ID."""
        clean_id = overlap_id.strip()
        try:
            from app.db import get_overlaps_collection
            coll = get_overlaps_collection()
            doc = coll.find_one({"overlap_id": clean_id})
            if doc:
                doc.pop("_id", None)
                return RegulatoryOverlap.model_validate(doc)
        except Exception:
            pass

        fp = self.overlaps_dir / f"{clean_id}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return RegulatoryOverlap.model_validate(json.load(f))
            except Exception:
                pass
        return None

    def get_overlaps(
        self,
        authority: Optional[str] = None,
        relationship_type: Optional[str] = None,
        topic: Optional[str] = None,
        status: Optional[str] = None,
        confidence: Optional[str] = None,
        requirement_id: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RegulatoryOverlap]:
        """Queries regulatory overlaps with multi-dimensional filtering and pagination."""
        query: Dict[str, Any] = {}
        if authority:
            auth_clean = authority.strip().upper()
            query["$or"] = [
                {"left_authority": auth_clean},
                {"right_authority": auth_clean}
            ]
        if relationship_type:
            query["relationship_type"] = relationship_type.strip()
        if topic:
            query["shared_topic"] = topic.strip().upper()
        if status:
            query["status"] = status.strip().upper()
        if confidence:
            query["confidence"] = confidence.strip().upper()
        if requirement_id:
            req_clean = requirement_id.strip()
            query["$or"] = [
                {"left_requirement_id": req_clean},
                {"right_requirement_id": req_clean}
            ]
        if document_id:
            doc_clean = document_id.strip()
            query["$or"] = [
                {"left_document_id": doc_clean},
                {"right_document_id": doc_clean}
            ]

        try:
            from app.db import get_overlaps_collection
            coll = get_overlaps_collection()
            cursor = coll.find(query).sort("created_at", -1).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryOverlap.model_validate(doc))
            if results or coll.count_documents(query) > 0:
                return results
        except Exception:
            pass

        # Local filesystem fallback
        overlaps = []
        for fp in self.overlaps_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    ovl = RegulatoryOverlap.model_validate(json.load(f))
                    if authority:
                        auth_c = authority.strip().upper()
                        if ovl.left_authority.upper() != auth_c and ovl.right_authority.upper() != auth_c:
                            continue
                    if relationship_type and ovl.relationship_type != relationship_type.strip():
                        continue
                    if topic and (ovl.shared_topic or "").upper() != topic.strip().upper():
                        continue
                    if status and ovl.status != status.strip().upper():
                        continue
                    if confidence and ovl.confidence != confidence.strip().upper():
                        continue
                    if requirement_id:
                        rc = requirement_id.strip()
                        if ovl.left_requirement_id != rc and ovl.right_requirement_id != rc:
                            continue
                    if document_id:
                        dc = document_id.strip()
                        if ovl.left_document_id != dc and ovl.right_document_id != dc:
                            continue
                    overlaps.append(ovl)
            except Exception:
                continue

        overlaps.sort(key=lambda x: x.created_at, reverse=True)
        return overlaps[offset: offset + limit]

    # -------------------------------------------------------------------------
    # REGULATORY CONFLICTS PERSISTENCE (Phase 74)
    # -------------------------------------------------------------------------

    def save_conflicts(self, conflicts: List[RegulatoryConflict]) -> int:
        """Upserts regulatory conflicts to MongoDB Atlas and local filesystem."""
        if not conflicts:
            return 0

        count = 0
        for cnf in conflicts:
            try:
                fp = self.conflicts_dir / f"{cnf.conflict_id}.json"
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(cnf.model_dump(), f, indent=2, ensure_ascii=False)
                count += 1
            except Exception as e:
                logger.warning(f"Error saving conflict {cnf.conflict_id} locally: {e}")

        try:
            from app.db import get_conflicts_collection
            coll = get_conflicts_collection()
            for cnf in conflicts:
                coll.update_one(
                    {"conflict_id": cnf.conflict_id},
                    {"$set": cnf.model_dump()},
                    upsert=True
                )
        except Exception as e:
            logger.debug(f"MongoDB save_conflicts bypassed/failed: {e}")

        return count

    def get_conflict_by_id(self, conflict_id: str) -> Optional[RegulatoryConflict]:
        """Retrieves a single conflict record by ID."""
        clean_id = conflict_id.strip()
        try:
            from app.db import get_conflicts_collection
            coll = get_conflicts_collection()
            doc = coll.find_one({"conflict_id": clean_id})
            if doc:
                doc.pop("_id", None)
                return RegulatoryConflict.model_validate(doc)
        except Exception:
            pass

        fp = self.conflicts_dir / f"{clean_id}.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return RegulatoryConflict.model_validate(json.load(f))
            except Exception:
                pass
        return None

    def get_conflicts(
        self,
        authority: Optional[str] = None,
        conflict_type: Optional[str] = None,
        severity: Optional[str] = None,
        confidence: Optional[str] = None,
        resolution_status: Optional[str] = None,
        requirement_id: Optional[str] = None,
        obligation_id: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RegulatoryConflict]:
        """Queries regulatory conflicts with filtering and pagination."""
        query: Dict[str, Any] = {}
        if authority:
            auth_clean = authority.strip().upper()
            query["$or"] = [
                {"left_authority": auth_clean},
                {"right_authority": auth_clean}
            ]
        if conflict_type:
            query["conflict_type"] = conflict_type.strip()
        if severity:
            query["severity"] = severity.strip().upper()
        if confidence:
            query["confidence"] = confidence.strip().upper()
        if resolution_status:
            query["resolution_status"] = resolution_status.strip().upper()
        if requirement_id:
            rc = requirement_id.strip()
            query["$or"] = [
                {"left_requirement_id": rc},
                {"right_requirement_id": rc}
            ]
        if obligation_id:
            oc = obligation_id.strip()
            query["$or"] = [
                {"left_obligation_id": oc},
                {"right_obligation_id": oc}
            ]
        if document_id:
            dc = document_id.strip()
            query["$or"] = [
                {"left_document_id": dc},
                {"right_document_id": dc}
            ]

        try:
            from app.db import get_conflicts_collection
            coll = get_conflicts_collection()
            cursor = coll.find(query).sort("created_at", -1).skip(offset).limit(limit)
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(RegulatoryConflict.model_validate(doc))
            if results or coll.count_documents(query) > 0:
                return results
        except Exception:
            pass

        # Local filesystem fallback
        conflicts = []
        for fp in self.conflicts_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    cnf = RegulatoryConflict.model_validate(json.load(f))
                    if authority:
                        auth_c = authority.strip().upper()
                        if cnf.left_authority.upper() != auth_c and cnf.right_authority.upper() != auth_c:
                            continue
                    if conflict_type and cnf.conflict_type != conflict_type.strip():
                        continue
                    if severity and cnf.severity != severity.strip().upper():
                        continue
                    if confidence and cnf.confidence != confidence.strip().upper():
                        continue
                    if resolution_status and cnf.resolution_status != resolution_status.strip().upper():
                        continue
                    if requirement_id:
                        rc = requirement_id.strip()
                        if cnf.left_requirement_id != rc and cnf.right_requirement_id != rc:
                            continue
                    if obligation_id:
                        oc = obligation_id.strip()
                        if cnf.left_obligation_id != oc and cnf.right_obligation_id != oc:
                            continue
                    if document_id:
                        dc = document_id.strip()
                        if cnf.left_document_id != dc and cnf.right_document_id != dc:
                            continue
                    conflicts.append(cnf)
            except Exception:
                continue

        conflicts.sort(key=lambda x: x.created_at, reverse=True)
        return conflicts[offset: offset + limit]

    def update_conflict_status(
        self,
        conflict_id: str,
        new_status: str,
        reviewer_id: str,
        notes: Optional[str] = None
    ) -> Optional[RegulatoryConflict]:
        """
        Updates the human review resolution status of a conflict and appends an audit event (74.16, 74.18).
        """
        conflict = self.get_conflict_by_id(conflict_id)
        if not conflict:
            return None

        event = ConflictReviewEvent(
            reviewer_id=reviewer_id,
            previous_status=conflict.resolution_status,
            new_status=new_status,
            notes=notes
        )
        conflict.resolution_status = new_status
        conflict.review_history.append(event)
        conflict.updated_at = datetime.utcnow().isoformat()

        self.save_conflicts([conflict])
        return conflict

    def invalidate_stale_records_for_requirement(self, requirement_id: str) -> Dict[str, int]:
        """
        Marks overlapping and conflicting records as stale / superseded when a requirement changes (73.21, 74.24).
        """
        affected_overlaps = self.get_overlaps(requirement_id=requirement_id, limit=500)
        for ovl in affected_overlaps:
            ovl.status = "SUPERSEDED"
            ovl.updated_at = datetime.utcnow().isoformat()
        if affected_overlaps:
            self.save_overlaps(affected_overlaps)

        affected_conflicts = self.get_conflicts(requirement_id=requirement_id, limit=500)
        for cnf in affected_conflicts:
            cnf.resolution_status = "DISMISSED"
            cnf.review_history.append(ConflictReviewEvent(
                reviewer_id="system_change_propagation",
                previous_status=cnf.resolution_status,
                new_status="DISMISSED",
                notes=f"Requirement {requirement_id} was updated or superseded; re-evaluation required."
            ))
            cnf.updated_at = datetime.utcnow().isoformat()
        if affected_conflicts:
            self.save_conflicts(affected_conflicts)

        return {
            "invalidated_overlaps": len(affected_overlaps),
            "invalidated_conflicts": len(affected_conflicts)
        }


# Global singleton repository
_compliance_repo = ComplianceRepository()


def get_compliance_repository() -> ComplianceRepository:
    return _compliance_repo

