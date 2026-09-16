"""
Topic Normalization & Classification Service (Phase 73.5).

Maps regulatory requirement and obligation text deterministically into controlled
regulatory topics from CONTROLLED_REGULATORY_TOPICS.
"""

import re
from typing import Optional, List, Dict, Set
from app.compliance.overlap_models import CONTROLLED_REGULATORY_TOPICS

# Domain keyword lexicon for controlled topic classification
TOPIC_LEXICON: Dict[str, List[str]] = {
    "KYC": [
        "know your customer", "kyc", "c-kyc", "ckyc", "identity verification",
        "customer identification", "aadhaar", "pan verification", "v-cip", "vcip",
        "video customer identification", "beneficial owner"
    ],
    "AML": [
        "anti-money laundering", "aml", "pmla", "prevention of money laundering",
        "suspicious transaction", "str", "cash transaction report", "ctr",
        "terrorist financing", "cft", "financial intelligence unit", "fiu", "fiu-ind"
    ],
    "REPORTING": [
        "submit report", "periodic report", "quarterly return", "annual return",
        "monthly return", "prudential return", "regulatory reporting", "filing",
        "intimation", "statement of affairs", "compliance report", "supervisory return"
    ],
    "DISCLOSURE": [
        "disclose", "disclosure", "public disclosure", "website disclosure",
        "financial statements", "investor charter", "key fact statement", "kfs",
        "transparency", "material event", "advertisement code"
    ],
    "RISK_MANAGEMENT": [
        "risk management", "enterprise risk", "credit risk", "market risk",
        "operational risk", "liquidity risk", "stress testing", "var", "capital adequacy",
        "risk mitigation", "chief risk officer", "cro"
    ],
    "GOVERNANCE": [
        "board of directors", "governance", "independent director", "audit committee",
        "nomination committee", "key managerial personnel", "kmp", "fit and proper",
        "whistle blower", "code of conduct", "related party transaction"
    ],
    "RECORD_KEEPING": [
        "maintain records", "record keeping", "preservation of records", "preserve records",
        "retention period", "books of account", "audit trail", "storage of records",
        "maintain books", "maintain electronic records", "8 years", "5 years"
    ],
    "AUDIT": [
        "statutory audit", "internal audit", "concurrent audit", "compliance audit",
        "system audit", "cyber audit", "forensic audit", "auditor", "inspection"
    ],
    "CYBERSECURITY": [
        "cyber security", "cybersecurity", "cyber resilience", "information security",
        "infosec", "soc", "security operations center", "penetration testing",
        "vapt", "firewall", "encryption", "two-factor", "2fa", "mfa"
    ],
    "DATA_PROTECTION": [
        "data protection", "privacy", "data localization", "customer data",
        "confidentiality", "data storage", "storage of payment system data"
    ],
    "CUSTOMER_PROTECTION": [
        "customer protection", "policyholder protection", "grievance redressal",
        "complaints", "ombudsman", "turnaround time", "tat", "claim settlement",
        "unfair practice", "mis-selling"
    ],
    "CAPITAL": [
        "net worth", "capital requirement", "capital adequacy", "car", "crar",
        "minimum paid-up capital", "tier 1", "tier 2", "regulatory capital"
    ],
    "LIQUIDITY": [
        "liquidity coverage ratio", "lcr", "nsfr", "net stable funding",
        "cash reserve", "statutory liquidity", "slr", "crr", "asset liability"
    ],
    "INVESTMENT": [
        "investment guidelines", "exposure limit", "prudential exposure",
        "single borrower", "group borrower", "investment in equity", "g-sec", "treasury"
    ],
    "TRANSACTION_MONITORING": [
        "transaction monitoring", "penny drop", "instant bank account verification",
        "escrow account", "settlement cycle", "t+1", "t+2", "reconciliation"
    ],
    "LICENSING": [
        "license", "licensing", "grant of license", "cancellation of license",
        "surrender of license", "eligibility criteria for license"
    ],
    "REGISTRATION": [
        "registration certificate", "certificate of registration", "cor",
        "application for registration", "renewal of registration", "intermediary registration"
    ],
    "OUTSOURCING": [
        "outsourcing", "third party service provider", "cloud service provider",
        "core activities", "vendor management", "sub-contracting"
    ],
    "INCIDENT_REPORTING": [
        "incident reporting", "cyber incident", "root cause analysis", "rca",
        "report within 6 hours", "report within 24 hours", "breach notification"
    ]
}


def normalize_regulatory_topic(
    text: str,
    subject: Optional[str] = None,
    action: Optional[str] = None,
    object_: Optional[str] = None,
    default: str = "OTHER"
) -> str:
    """
    Deterministically normalizes regulatory requirement text into a controlled topic (73.5).
    Evaluates exact domain keywords against the combined requirement context.
    """
    combined = f"{text or ''} {subject or ''} {action or ''} {object_ or ''}".lower()

    # Score each controlled topic based on phrase matches
    scores: Dict[str, int] = {}
    for topic, keywords in TOPIC_LEXICON.items():
        score = 0
        for kw in keywords:
            if " " in kw:
                if kw in combined:
                    score += 3
            else:
                if re.search(rf"\b{re.escape(kw)}\b", combined):
                    score += 1
        if score > 0:
            scores[topic] = score

    if scores:
        best_topic = max(scores.items(), key=lambda x: x[1])[0]
        return best_topic

    return default
