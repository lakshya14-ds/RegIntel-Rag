"""
Scheduled Regulatory Alert & Intelligence Evaluation Jobs (Phase 65.11, 65.12).

Provides:
- evaluate_upcoming_effective_dates
- evaluate_upcoming_deadlines
- refresh_recurring_deadlines
- evaluate_checklist_impacts
- run_daily_regulatory_intelligence_job
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.compliance.repository import get_compliance_repository
from app.compliance.alert_engine import get_alert_engine
from app.compliance.deadline_engine import get_deadline_engine
from app.compliance.alert_models import RegulatoryAlert, RegulatoryDeadline

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class RegulatoryIntelligenceJobRunner:
    """
    Orchestrates daily intelligence jobs: scanning upcoming effective dates,
    refreshing recurring deadlines, detecting checklist impacts, and generating alerts.
    """

    def __init__(self):
        self.repo = get_compliance_repository()
        self.alert_engine = get_alert_engine()
        self.deadline_engine = get_deadline_engine()

    def run_daily_evaluation(self, as_of_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes complete daily regulatory intelligence evaluation (65.12).
        Produces structured alert candidates, deduplicates them, and dispatches in-app notifications.
        """
        ref_str = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")
        logger.info(f"Starting daily regulatory intelligence evaluation as of {ref_str}")

        # 1. Fetch active date events
        date_events = self.repo.get_date_events(limit=500)

        # 2. Fetch obligations and refresh deadlines
        obligations = self.repo.get_obligations(limit=500)
        new_deadlines: List[RegulatoryDeadline] = []
        for ob in obligations:
            extracted = self.deadline_engine.extract_deadlines_from_obligation(
                obligation=ob,
                as_of_date=ref_str,
                planning_window_days=180
            )
            new_deadlines.extend(extracted)

        self.repo.save_deadlines(new_deadlines)
        all_deadlines = self.repo.get_deadlines(limit=500)

        # 3. Evaluate Alerts
        generated_alerts: List[RegulatoryAlert] = []

        # (a) Upcoming Effective Dates
        eff_alerts = self.alert_engine.evaluate_upcoming_effective_dates(
            date_events=date_events,
            as_of_date=ref_str
        )
        generated_alerts.extend(eff_alerts)

        # (b) Upcoming Deadlines
        ddl_alerts = self.alert_engine.evaluate_upcoming_deadlines(
            deadlines=all_deadlines,
            as_of_date=ref_str
        )
        generated_alerts.extend(ddl_alerts)

        # (c) Checklist impacts
        checklists = self.repo.get_checklists(limit=100)
        for chk in checklists:
            for ev in date_events:
                if ev.document_id in chk.document_ids and ev.event_type == "EFFECTIVE":
                    chk_alert = self.alert_engine.evaluate_checklist_impact_alerts(
                        checklist=chk,
                        changed_document_id=ev.document_id,
                        effective_date=ev.date,
                        as_of_date=ref_str
                    )
                    if chk_alert:
                        generated_alerts.append(chk_alert)

        # 4. Save & Deduplicate
        saved_count = self.repo.save_alerts(generated_alerts)

        # 5. Dispatch in-app notifications for newly persisted alerts
        for alt in generated_alerts:
            self.alert_engine.notifier.send(alt, channel="IN_APP")

        logger.info(f"Evaluation complete. Generated {len(generated_alerts)} alert candidates, {saved_count} newly persisted.")
        return {
            "as_of_date": ref_str,
            "date_events_evaluated": len(date_events),
            "obligations_evaluated": len(obligations),
            "deadlines_refreshed": len(new_deadlines),
            "alert_candidates_generated": len(generated_alerts),
            "new_alerts_saved": saved_count
        }


_global_job_runner = RegulatoryIntelligenceJobRunner()


def get_job_runner() -> RegulatoryIntelligenceJobRunner:
    return _global_job_runner
