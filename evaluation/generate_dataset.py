"""
Script to generate benchmark evaluation dataset for RegIntel RAG using real corpus document IDs and chunk IDs.
"""

import json
import glob
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

# Document IDs:
# 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8 -> Master Circular for Investment Advisers (IAs)
# 555ddaa81bc0ec0847a73444a40b7ce65ac7f7c9b44ddd3b9cf0d59e7f86b06b -> Master Circular For Mutual Funds
# d79215cbdbca03367cdfdcfe77df2d8f788619371bc2dc4f72dd98eac72ac6bf -> Master Circular For Stock Brokers
# f9ec4356c36ad999c9e1088a6c0c28c4de85ccb5ccd8bc65c98bec8454c42c66 -> Master Circular For Research Analysts
# d34cf5aff0780724741a4d2e5d4f2a62b9d3b2a6b4af62f6400b492ead5dbeee -> Master Circular For Depositories
# 20518434fd1c3354786dc7e3b070553c266321c6f89ca971376d0d1ac64d3b4a -> Introduction Of Beta Version Of T 0 Settlement
# b50dcc4966fb18892911ab18c9699431ad365ed2b12ba5d86e03d060a771fda5 -> Mandating Additional Disclosures By FPIs
# be8461b8d553b86c321ad3affeac24c3acc57a045768ee24caf48d9d2924cb47 -> Framework For KYC Registration Agencies KRAs
# 1ef425b69756aeab54d52eecd7f9e26b0802ad23c04891eb8e32860e576b1c72 -> Standard Operating Procedure For Inter Operable Sandbox
# 6ca36ed21933573c6cfcf46873a202d604d156dc8fc6af55d0c04394961124ff -> Financial Disincentive For Surveillance Lapses
# 03dd333e09b21448a64bf9aac73fd1fde91b137f36937edf51dee1f99d54e7da -> Overseas Investment By Mutual Funds

# Load chunks to get exact chunk IDs
doc_chunks = {}
for f in glob.glob("data/processed/chunks/*.json"):
    data = json.load(open(f, encoding="utf-8"))
    did = data["document_id"]
    doc_chunks[did] = [c["chunk_id"] for c in data["chunks"]]

DOC_IA_MASTER = "69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"
DOC_MF_MASTER = "555ddaa81bc0ec0847a73444a40b7ce65ac7f7c9b44ddd3b9cf0d59e7f86b06b"
DOC_BROKER_MASTER = "d79215cbdbca03367cdfdcfe77df2d8f788619371bc2dc4f72dd98eac72ac6bf"
DOC_RA_MASTER = "f9ec4356c36ad999c9e1088a6c0c28c4de85ccb5ccd8bc65c98bec8454c42c66"
DOC_DEP_MASTER = "d34cf5aff0780724741a4d2e5d4f2a62b9d3b2a6b4af62f6400b492ead5dbeee"
DOC_T0_SETTLE = "20518434fd1c3354786dc7e3b070553c266321c6f89ca971376d0d1ac64d3b4a"
DOC_FPI_DISC = "b50dcc4966fb18892911ab18c9699431ad365ed2b12ba5d86e03d060a771fda5"
DOC_KRA = "be8461b8d553b86c321ad3affeac24c3acc57a045768ee24caf48d9d2924cb47"
DOC_SANDBOX = "1ef425b69756aeab54d52eecd7f9e26b0802ad23c04891eb8e32860e576b1c72"
DOC_SURVEILLANCE = "6ca36ed21933573c6cfcf46873a202d604d156dc8fc6af55d0c04394961124ff"
DOC_OVERSEAS_MF = "03dd333e09b21448a64bf9aac73fd1fde91b137f36937edf51dee1f99d54e7da"
DOC_IA_IFSC = "384edf54c1afbbf95237706cd2f5ca9f6742a0788056126b70baa6efb193c2c1"
DOC_IA_TWEAKS = "af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
DOC_UNAUTH_EFT = "6dc7cd6f0e1b0643b116f473b616db61cda6d95bfb006f2c29aa1d385db352c4"

# 1. RETRIEVAL QUESTIONS (50 Questions across 10 categories)
retrieval_questions = [
    # 1. Factual retrieval
    {"id": "R001", "question": "What are the record keeping requirements for investment advisers under SEBI regulations?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "factual"},
    {"id": "R002", "question": "What are the annual compliance audit timelines for registered investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "factual"},
    {"id": "R003", "question": "What is the fee cap structure specified under Regulation 15A for investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "factual"},
    {"id": "R004", "question": "What are the qualification and certification norms for research analysts?", "expected_documents": [DOC_RA_MASTER], "expected_chunks": doc_chunks.get(DOC_RA_MASTER, [])[:3], "category": "factual"},
    {"id": "R005", "question": "What are the KYC verification responsibilities of KYC Registration Agencies KRAs?", "expected_documents": [DOC_KRA], "expected_chunks": doc_chunks.get(DOC_KRA, [])[:3], "category": "factual"},

    # 2. Exact regulatory terminology
    {"id": "R006", "question": "What does BSE Administration and Supervision Limited BASL administer for investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "exact_terminology"},
    {"id": "R007", "question": "How is Online Bond Platform Provider OBPP governed under SEBI master circular?", "expected_documents": [DOC_BROKER_MASTER], "expected_chunks": doc_chunks.get(DOC_BROKER_MASTER, [])[:3], "category": "exact_terminology"},
    {"id": "R008", "question": "What are the Designated Depository Participants DDP reporting formats?", "expected_documents": [DOC_DEP_MASTER], "expected_chunks": doc_chunks.get(DOC_DEP_MASTER, [])[:3], "category": "exact_terminology"},
    {"id": "R009", "question": "What is the Inter Operable Regulatory Sandbox IoRS framework under SEBI?", "expected_documents": [DOC_SANDBOX], "expected_chunks": doc_chunks.get(DOC_SANDBOX, [])[:3], "category": "exact_terminology"},
    {"id": "R010", "question": "What is the Total Expense Ratio TER disclosure requirement for mutual funds?", "expected_documents": [DOC_MF_MASTER], "expected_chunks": doc_chunks.get(DOC_MF_MASTER, [])[:3], "category": "exact_terminology"},

    # 3. Regulation/circular number
    {"id": "R011", "question": "What does SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2024/56 specify for investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "circular_number"},
    {"id": "R012", "question": "What is mandated under Regulation 15A of SEBI Investment Advisers Regulations?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "circular_number"},
    {"id": "R013", "question": "What are the provisions in Master Circular SEBI/HO/AFD/PoD/CIR/2024/001 for mutual funds?", "expected_documents": [DOC_MF_MASTER], "expected_chunks": doc_chunks.get(DOC_MF_MASTER, [])[:3], "category": "circular_number"},
    {"id": "R014", "question": "What are the requirements under SEBI Master Circular for Stock Brokers?", "expected_documents": [DOC_BROKER_MASTER], "expected_chunks": doc_chunks.get(DOC_BROKER_MASTER, [])[:3], "category": "circular_number"},
    {"id": "R015", "question": "What circular governs the Beta Version of T+0 Settlement?", "expected_documents": [DOC_T0_SETTLE], "expected_chunks": doc_chunks.get(DOC_T0_SETTLE, [])[:3], "category": "circular_number"},

    # 4. Current requirement
    {"id": "R016", "question": "What are the current client agreement requirements for registered investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "current_requirement"},
    {"id": "R017", "question": "What are the current net worth criteria for non-individual investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "current_requirement"},
    {"id": "R018", "question": "What are the current disclosure norms for Foreign Portfolio Investors FPIs?", "expected_documents": [DOC_FPI_DISC], "expected_chunks": doc_chunks.get(DOC_FPI_DISC, [])[:3], "category": "current_requirement"},
    {"id": "R019", "question": "What are the current surveillance lapse financial disincentives for market intermediaries?", "expected_documents": [DOC_SURVEILLANCE], "expected_chunks": doc_chunks.get(DOC_SURVEILLANCE, [])[:3], "category": "current_requirement"},
    {"id": "R020", "question": "What are the current risk profiling requirements before offering investment advice?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "current_requirement"},

    # 5. Latest requirement
    {"id": "R021", "question": "What are the latest SEBI requirements for investment advisers in 2024?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "latest_requirement"},
    {"id": "R022", "question": "What are the latest overseas investment limits and framework for mutual funds?", "expected_documents": [DOC_OVERSEAS_MF, DOC_MF_MASTER], "expected_chunks": doc_chunks.get(DOC_OVERSEAS_MF, [])[:3], "category": "latest_requirement"},
    {"id": "R023", "question": "What are the latest rules on Beta Version of T+0 Settlement cycle in India?", "expected_documents": [DOC_T0_SETTLE], "expected_chunks": doc_chunks.get(DOC_T0_SETTLE, [])[:3], "category": "latest_requirement"},
    {"id": "R024", "question": "What are the latest measures to safeguard investors against unauthorized electronic fund transfers?", "expected_documents": [DOC_UNAUTH_EFT], "expected_chunks": doc_chunks.get(DOC_UNAUTH_EFT, [])[:3], "category": "latest_requirement"},
    {"id": "R025", "question": "What is the latest operating guideline for investment advisers in IFSC GIFT City?", "expected_documents": [DOC_IA_IFSC], "expected_chunks": doc_chunks.get(DOC_IA_IFSC, [])[:3], "category": "latest_requirement"},

    # 6. Effective date
    {"id": "R026", "question": "When did the Master Circular for Investment Advisers become effective in May 2024?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "effective_date"},
    {"id": "R027", "question": "When was the Beta version of T+0 settlement launched by SEBI?", "expected_documents": [DOC_T0_SETTLE], "expected_chunks": doc_chunks.get(DOC_T0_SETTLE, [])[:3], "category": "effective_date"},
    {"id": "R028", "question": "When did the additional disclosure requirements for FPIs come into force?", "expected_documents": [DOC_FPI_DISC], "expected_chunks": doc_chunks.get(DOC_FPI_DISC, [])[:3], "category": "effective_date"},
    {"id": "R029", "question": "What is the timeline for compliance audit submission by investment advisers?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "effective_date"},
    {"id": "R030", "question": "When was the Master Circular for Research Analysts published?", "expected_documents": [DOC_RA_MASTER], "expected_chunks": doc_chunks.get(DOC_RA_MASTER, [])[:3], "category": "effective_date"},

    # 7. Category-specific
    {"id": "R031", "question": "What are the regulatory guidelines specific to Mutual Funds?", "expected_documents": [DOC_MF_MASTER], "expected_chunks": doc_chunks.get(DOC_MF_MASTER, [])[:3], "category": "category_specific"},
    {"id": "R032", "question": "What are the compliance duties of Stock Brokers under SEBI Master Circular?", "expected_documents": [DOC_BROKER_MASTER], "expected_chunks": doc_chunks.get(DOC_BROKER_MASTER, [])[:3], "category": "category_specific"},
    {"id": "R033", "question": "What code of conduct applies specifically to Research Analysts?", "expected_documents": [DOC_RA_MASTER], "expected_chunks": doc_chunks.get(DOC_RA_MASTER, [])[:3], "category": "category_specific"},
    {"id": "R034", "question": "What are the obligations of Depositories and Depository Participants under SEBI?", "expected_documents": [DOC_DEP_MASTER], "expected_chunks": doc_chunks.get(DOC_DEP_MASTER, [])[:3], "category": "category_specific"},
    {"id": "R035", "question": "What are the specific guidelines for investment advisers operating in IFSC?", "expected_documents": [DOC_IA_IFSC], "expected_chunks": doc_chunks.get(DOC_IA_IFSC, [])[:3], "category": "category_specific"},

    # 8. Historical query
    {"id": "R036", "question": "What were the previous tweaks in the regulatory framework for investment advisers issued in 2021?", "expected_documents": [DOC_IA_TWEAKS], "expected_chunks": doc_chunks.get(DOC_IA_TWEAKS, [])[:3], "category": "historical"},
    {"id": "R037", "question": "What were the earlier guidelines for investment advisers issued in September 2020?", "expected_documents": [DOC_IA_TWEAKS, DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_TWEAKS, [])[:3], "category": "historical"},
    {"id": "R038", "question": "What was the previous method of settlement prior to T+0 beta rollout?", "expected_documents": [DOC_T0_SETTLE], "expected_chunks": doc_chunks.get(DOC_T0_SETTLE, [])[:3], "category": "historical"},
    {"id": "R039", "question": "How did KYC registration work before KRA framework enhancements?", "expected_documents": [DOC_KRA], "expected_chunks": doc_chunks.get(DOC_KRA, [])[:3], "category": "historical"},
    {"id": "R040", "question": "What were the historical investment limits for mutual funds investing overseas?", "expected_documents": [DOC_OVERSEAS_MF, DOC_MF_MASTER], "expected_chunks": doc_chunks.get(DOC_OVERSEAS_MF, [])[:3], "category": "historical"},

    # 9. Source-specific query
    {"id": "R041", "question": "What circulars has SEBI issued regarding investment advisory regulation?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "source_specific"},
    {"id": "R042", "question": "What directives are issued by SEBI for depositories in India?", "expected_documents": [DOC_DEP_MASTER], "expected_chunks": doc_chunks.get(DOC_DEP_MASTER, [])[:3], "category": "source_specific"},
    {"id": "R043", "question": "What are the SEBI rules for surveillance related lapses by market infrastructure institutions?", "expected_documents": [DOC_SURVEILLANCE], "expected_chunks": doc_chunks.get(DOC_SURVEILLANCE, [])[:3], "category": "source_specific"},
    {"id": "R044", "question": "What SEBI guidelines apply to interoperable regulatory sandboxes?", "expected_documents": [DOC_SANDBOX], "expected_chunks": doc_chunks.get(DOC_SANDBOX, [])[:3], "category": "source_specific"},
    {"id": "R045", "question": "What SEBI circular mandates additional disclosures for high risk FPIs?", "expected_documents": [DOC_FPI_DISC], "expected_chunks": doc_chunks.get(DOC_FPI_DISC, [])[:3], "category": "source_specific"},

    # 10. Difficult semantic query
    {"id": "R046", "question": "How are conflicts of interest separated between fee-based advice and distribution services?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "difficult_semantic"},
    {"id": "R047", "question": "What happens when an investor experiences an unauthorized electronic transaction?", "expected_documents": [DOC_UNAUTH_EFT], "expected_chunks": doc_chunks.get(DOC_UNAUTH_EFT, [])[:3], "category": "difficult_semantic"},
    {"id": "R048", "question": "What financial penalties are levied on stock exchanges for delayed trade surveillance reporting?", "expected_documents": [DOC_SURVEILLANCE], "expected_chunks": doc_chunks.get(DOC_SURVEILLANCE, [])[:3], "category": "difficult_semantic"},
    {"id": "R049", "question": "Can an individual investment adviser provide execution services to the same advisory client?", "expected_documents": [DOC_IA_MASTER], "expected_chunks": doc_chunks.get(DOC_IA_MASTER, [])[:3], "category": "difficult_semantic"},
    {"id": "R050", "question": "What mechanism is available for fintech entities testing cross-sectoral innovative financial products?", "expected_documents": [DOC_SANDBOX], "expected_chunks": doc_chunks.get(DOC_SANDBOX, [])[:3], "category": "difficult_semantic"}
]

# 2. GENERATION QUESTIONS (30 Questions: 20 Answerable, 5 Partially Answerable, 5 Unanswerable)
generation_questions = [
    # Answerable
    {"id": "G001", "question": "What are the record keeping requirements for Investment Advisers under SEBI regulations?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "Investment Advisers must maintain books of accounts, agreements, and advice records for a minimum period of 8 years and complete an annual compliance audit within 6 months of the financial year end."},
    {"id": "G002", "question": "What is the fee limit mandated under Regulation 15A for investment advisers?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "Fees charged by an Investment Adviser must not exceed the regulatory caps specified in Regulation 15A of the SEBI Investment Advisers Regulations."},
    {"id": "G003", "question": "What is the Beta Version of T+0 Settlement introduced by SEBI?", "answerability": "ANSWERABLE", "expected_sources": [DOC_T0_SETTLE], "reference_answer": "SEBI introduced a beta version of optional T+0 settlement for a limited set of 25 scrips with a limited number of brokers to enable same-day trade settlement."},
    {"id": "G004", "question": "What are the qualification requirements for principal officers of Investment Advisers?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "Principal officers of non-individual IAs must hold a professional qualification or postgraduate degree in finance, accountancy, or capital markets and valid NISM certifications."},
    {"id": "G005", "question": "What is the role of BSE Administration and Supervision Limited BASL?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "BASL acts as the recognized body for administration and supervision of registered Investment Advisers under SEBI supervision."},
    {"id": "G006", "question": "What are the KYC obligations enforced by KYC Registration Agencies KRAs?", "answerability": "ANSWERABLE", "expected_sources": [DOC_KRA], "reference_answer": "KRAs are required to upload, maintain, and verify KYC records of clients centrally for capital market intermediaries."},
    {"id": "G007", "question": "What is the Inter-Operable Regulatory Sandbox IoRS?", "answerability": "ANSWERABLE", "expected_sources": [DOC_SANDBOX], "reference_answer": "IoRS is a coordinated testing mechanism set up by financial sector regulators (RBI, SEBI, IRDAI, IFSCA, PFRDA) for innovative fintech products spanning multiple jurisdictions."},
    {"id": "G008", "question": "What are the additional disclosure mandates for high risk Foreign Portfolio Investors?", "answerability": "ANSWERABLE", "expected_sources": [DOC_FPI_DISC], "reference_answer": "FPIs meeting specified concentration criteria must provide granular ownership disclosures down to the natural person level."},
    {"id": "G009", "question": "What are the rules regarding investment advisory agreements with clients?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "Investment Advisers must enter into an advisory agreement detailing terms, fees, risk profiling, and conflict resolution before rendering advice."},
    {"id": "G010", "question": "What are the financial disincentives imposed for surveillance related lapses?", "answerability": "ANSWERABLE", "expected_sources": [DOC_SURVEILLANCE], "reference_answer": "SEBI prescribes structured financial penalties on Market Infrastructure Institutions for lapses or delays in alert generation and surveillance reporting."},
    {"id": "G011", "question": "Can an Investment Adviser receive distribution commissions from mutual funds for recommended schemes?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "No, registered Investment Advisers and their family members/entities cannot accept commissions or distribution fees from products recommended to advisory clients."},
    {"id": "G012", "question": "What is the overseas investment framework for Indian Mutual Funds?", "answerability": "ANSWERABLE", "expected_sources": [DOC_OVERSEAS_MF, DOC_MF_MASTER], "reference_answer": "Mutual Funds can invest in overseas securities, mutual funds, and unit trusts within the industry-wide aggregate cap specified by SEBI and RBI."},
    {"id": "G013", "question": "What safeguards are required against unauthorized electronic fund transfers?", "answerability": "ANSWERABLE", "expected_sources": [DOC_UNAUTH_EFT], "reference_answer": "Market intermediaries must establish automated alerting, multi-factor authentication, and designated grievance resolution mechanisms for unauthorized transfers."},
    {"id": "G014", "question": "What are the operating guidelines for Investment Advisers in IFSC GIFT City?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_IFSC], "reference_answer": "Investment Advisers in IFSC are permitted to provide advisory services to non-resident investors and eligible Indian entities subject to IFSCA/SEBI guidelines."},
    {"id": "G015", "question": "What are the research report disclosure rules for Research Analysts?", "answerability": "ANSWERABLE", "expected_sources": [DOC_RA_MASTER], "reference_answer": "Research Analysts must disclose their financial interest, shareholding, and any business relationships with the subject company in their research reports."},
    {"id": "G016", "question": "What are the compliance audit requirements for Stock Brokers?", "answerability": "ANSWERABLE", "expected_sources": [DOC_BROKER_MASTER], "reference_answer": "Stock Brokers must undergo periodic internal and system audits by independent certified auditors to verify regulatory compliance."},
    {"id": "G017", "question": "What are the risk profiling obligations before offering investment advice?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "IAs must assess client risk appetite, investment goals, age, income, and past experience before recommending any financial product."},
    {"id": "G018", "question": "What are the requirements for Online Bond Platform Providers OBPP?", "answerability": "ANSWERABLE", "expected_sources": [DOC_BROKER_MASTER], "reference_answer": "OBPPs must be registered as stock brokers in the debt segment and route transactions through exchange settlement mechanisms."},
    {"id": "G019", "question": "What is the timeline for depositories to resolve investor grievances?", "answerability": "ANSWERABLE", "expected_sources": [DOC_DEP_MASTER], "reference_answer": "Depositories and depository participants must redress investor grievances within stipulated SEBI turnaround times."},
    {"id": "G020", "question": "What constitutes a family of client under SEBI IA regulations?", "answerability": "ANSWERABLE", "expected_sources": [DOC_IA_MASTER], "reference_answer": "A client family includes the individual client, their spouse, dependent children, and dependent parents for advice and fee calculation purposes."},

    # Partially Answerable
    {"id": "G021", "question": "What are the exact cryptocurrency trading rules and taxation guidelines under SEBI circulars?", "answerability": "PARTIALLY_ANSWERABLE", "expected_sources": [DOC_BROKER_MASTER], "reference_answer": "SEBI regulations in the corpus cover traditional securities markets and intermediaries, but do not provide cryptocurrency trading or taxation guidelines."},
    {"id": "G022", "question": "What are the algorithmic trading co-location latency thresholds and hardware specifications under SEBI Master Circular for Stock Brokers?", "answerability": "PARTIALLY_ANSWERABLE", "expected_sources": [DOC_BROKER_MASTER], "reference_answer": "The circular covers broker compliance and technology governance, but specific vendor hardware latency thresholds are governed by exchange-level specifications."},
    {"id": "G023", "question": "What are the foreign exchange remittance tax rates for overseas investments by Mutual Funds?", "answerability": "PARTIALLY_ANSWERABLE", "expected_sources": [DOC_OVERSEAS_MF], "reference_answer": "SEBI circulars define overseas investment eligibility and fund limits, while tax rates are governed by Indian Income Tax and RBI FEMA rules."},
    {"id": "G024", "question": "What are the capital requirements for insurance brokers under IRDAI regulations?", "answerability": "PARTIALLY_ANSWERABLE", "expected_sources": [], "reference_answer": "The indexed corpus contains SEBI securities market circulars; insurance broker capital requirements fall under IRDAI regulations."},
    {"id": "G025", "question": "How does SEBI regulate commodity derivatives warehouse receipts for agricultural commodities?", "answerability": "PARTIALLY_ANSWERABLE", "expected_sources": [DOC_DEP_MASTER], "reference_answer": "Depositories maintain electronic warehouse receipts, but detailed agricultural warehouse standards are governed by WDRA/commodity rules."},

    # Unanswerable
    {"id": "G026", "question": "What is the prescribed medical negligence penalty under the Medical Council of India guidelines?", "answerability": "UNANSWERABLE", "expected_sources": [], "reference_answer": "I could not find sufficient evidence in the indexed regulatory sources."},
    {"id": "G027", "question": "What are the FDA approval timelines for pharmaceutical clinical trials in the United States?", "answerability": "UNANSWERABLE", "expected_sources": [], "reference_answer": "I could not find sufficient evidence in the indexed regulatory sources."},
    {"id": "G028", "question": "What are the aviation safety guidelines issued by the Federal Aviation Administration FAA for Boeing 737 Max?", "answerability": "UNANSWERABLE", "expected_sources": [], "reference_answer": "I could not find sufficient evidence in the indexed regulatory sources."},
    {"id": "G029", "question": "What are the minimum capital adequacy ratios for European Union banks under Basel III framework?", "answerability": "UNANSWERABLE", "expected_sources": [], "reference_answer": "I could not find sufficient evidence in the indexed regulatory sources."},
    {"id": "G030", "question": "What are the environmental emission caps for coal thermal power plants under the EPA Clean Air Act?", "answerability": "UNANSWERABLE", "expected_sources": [], "reference_answer": "I could not find sufficient evidence in the indexed regulatory sources."}
]

# 3. COMPARISON CASES (10 cases)
comparison_cases = [
    {
        "id": "C001",
        "case_name": "Investment Advisers IFSC vs Tweaks Circular",
        "document_a": DOC_IA_TWEAKS,
        "document_b": DOC_IA_IFSC,
        "synthetic_test_case": False,
        "expected_modifications": ["Operating guidelines for IFSC jurisdiction", "Client scope"],
        "description": "Compares general IA framework tweaks against specialized IFSC operating guidelines."
    },
    {
        "id": "C002",
        "case_name": "Investment Advisers 2020 Guidelines vs 2024 Master Circular",
        "document_a": "3edbbaf8019cab2985b9e7f77846cee64bd988a82dc0a8998ad54f549632e2ac",
        "document_b": DOC_IA_MASTER,
        "synthetic_test_case": False,
        "expected_modifications": ["Record keeping", "Fee limits", "Registration norms"],
        "description": "Compares initial 2020 IA guidelines against consolidated 2024 Master Circular."
    },
    {
        "id": "C003",
        "case_name": "Mutual Funds Overseas Investment vs Master Circular",
        "document_a": DOC_OVERSEAS_MF,
        "document_b": DOC_MF_MASTER,
        "synthetic_test_case": False,
        "expected_modifications": ["Overseas fund limits", "Valuation methodology"],
        "description": "Compares specific overseas fund circular with consolidated mutual fund master circular."
    },
    {
        "id": "C004",
        "case_name": "Mutual Funds Overseas ETF vs Overseas Mutual Fund Framework",
        "document_a": "a3bb0f0f46f233a251e591423f937c39cd3d9dade0ce20644ff39d0551e75007",
        "document_b": DOC_OVERSEAS_MF,
        "synthetic_test_case": False,
        "expected_modifications": ["Overseas ETF eligibility", "Fund manager caps"],
        "description": "Compares two consecutive overseas investment framework circulars."
    },
    {
        "id": "C005",
        "case_name": "Stock Brokers Master Circular vs Surveillance Lapses",
        "document_a": DOC_SURVEILLANCE,
        "document_b": DOC_BROKER_MASTER,
        "synthetic_test_case": False,
        "expected_modifications": ["Surveillance penalty clauses", "Reporting deadlines"],
        "description": "Compares dedicated surveillance penalty circular with broad Stock Brokers Master Circular."
    },
    {
        "id": "C006",
        "case_name": "Depositories Master Circular vs Depository Reporting",
        "document_a": "b4161c3dc5d587f30868606394a2277fc54e0d8bc2bc1722f361df49e4558089",
        "document_b": DOC_DEP_MASTER,
        "synthetic_test_case": False,
        "expected_modifications": ["DDP reporting formats", "Depository compliance"],
        "description": "Compares dedicated DDP reporting circular with Master Circular for Depositories."
    },
    {
        "id": "C007",
        "case_name": "Mutual Funds Disclosures vs MF Master Circular",
        "document_a": "db53a3a3dc6858093ed3b00c215376239a9bd0f5cf920af98656d48e8675a1f2",
        "document_b": DOC_MF_MASTER,
        "synthetic_test_case": False,
        "expected_modifications": ["Additional portfolio disclosures", "TER reporting"],
        "description": "Compares standalone additional disclosure circular with Mutual Funds Master Circular."
    },
    {
        "id": "C008",
        "case_name": "FPI Disclosures vs Stock Broker Compliance",
        "document_a": DOC_FPI_DISC,
        "document_b": DOC_BROKER_MASTER,
        "synthetic_test_case": False,
        "expected_modifications": ["High risk FPI granular disclosures", "Broker onboarding"],
        "description": "Compares FPI disclosure circular with broker client onboarding norms."
    },
    {
        "id": "C009",
        "case_name": "Synthetic Baseline vs Synthetic Revised IA Net Worth",
        "document_a": "synthetic_doc_ia_2020",
        "document_b": "synthetic_doc_ia_2024",
        "synthetic_test_case": True,
        "expected_modifications": ["Net worth increased from 25L to 50L", "Digital audit added"],
        "description": "Controlled synthetic test case comparing numerical net worth threshold change."
    },
    {
        "id": "C010",
        "case_name": "Synthetic Baseline vs Synthetic Revised T+0 Settlement",
        "document_a": "synthetic_settle_t1",
        "document_b": "synthetic_settle_t0",
        "synthetic_test_case": True,
        "expected_modifications": ["Settlement cycle reduced from T+1 to T+0", "25 scrips eligible"],
        "description": "Controlled synthetic test case comparing settlement cycle transition."
    }
]

# Write to files
with open(DATASET_DIR / "retrieval_questions.json", "w", encoding="utf-8") as f:
    json.dump(retrieval_questions, f, indent=2)

with open(DATASET_DIR / "generation_questions.json", "w", encoding="utf-8") as f:
    json.dump(generation_questions, f, indent=2)

with open(DATASET_DIR / "comparison_cases.json", "w", encoding="utf-8") as f:
    json.dump(comparison_cases, f, indent=2)

print("Generated benchmark datasets successfully:")
print(f"- retrieval_questions.json : {len(retrieval_questions)} questions")
print(f"- generation_questions.json: {len(generation_questions)} questions")
print(f"- comparison_cases.json   : {len(comparison_cases)} cases")
