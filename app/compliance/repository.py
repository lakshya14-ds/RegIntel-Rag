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
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import settings
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class ComplianceRepository:
    """
    Manages database and filesystem persistence for requirements, obligations, and checklists.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_data_dir = data_dir or (settings.processed_data_dir / "compliance")
        self.req_dir = self.base_data_dir / "requirements"
        self.ob_dir = self.base_data_dir / "obligations"
        self.chk_dir = self.base_data_dir / "checklists"

        # Ensure local fallback storage directories exist
        self.req_dir.mkdir(parents=True, exist_ok=True)
        self.ob_dir.mkdir(parents=True, exist_ok=True)
        self.chk_dir.mkdir(parents=True, exist_ok=True)

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

    def get_checklists(self, limit: int = 50, offset: int = 0) -> List[ComplianceChecklist]:
        """Lists saved compliance checklists."""
        try:
            from app.db import get_checklists_collection
            coll = get_checklists_collection()
            cursor = coll.find({}).sort("updated_at", -1).skip(offset).limit(limit)
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


# Global singleton repository
_compliance_repo = ComplianceRepository()


def get_compliance_repository() -> ComplianceRepository:
    return _compliance_repo
