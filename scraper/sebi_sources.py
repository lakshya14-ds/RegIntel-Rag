"""
SEBI Seed URLs and Curated Document Sources for Initial Ingestion.

Covers four key regulatory domains:
1. Investment Advisers (IA)
2. Mutual Funds (MF)
3. Market Intermediaries (MIRSD)
4. Securities Markets / Listing Regulations (LODR / PIT)
"""

from typing import List, Dict, Any

# Authoritative Listing / Section Seed URLs on SEBI Portal
SEBI_LISTING_URLS: List[str] = [
    # Main Circulars Listing Page
    "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0",
    # Master Circulars
    "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=1",
]

# Curated high-value SEBI regulatory circulars and documents across key domains
SEBI_DOCUMENT_URLS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. Investment Advisers & Research Analysts
    # -------------------------------------------------------------
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2024/master-circular-for-investment-advisers-ias-_83556.html",
        "title": "Master Circular for Investment Advisers (IAs)",
        "expected_category": "Investment Adviser",
        "date_hint": "2024-05-24"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2024/master-circular-for-research-analysts_83555.html",
        "title": "Master Circular for Research Analysts",
        "expected_category": "Investment Adviser",
        "date_hint": "2024-05-24"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jan-2024/guidelines-for-investment-advisers-ias-_80721.html",
        "title": "Guidelines for Investment Advisers - Framework for Administration and Supervision",
        "expected_category": "Investment Adviser",
        "date_hint": "2024-01-16"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/sep-2020/operating-guidelines-for-investment-advisers-in-international-financial-services-centre-ifsc-_47545.html",
        "title": "Operating Guidelines for Investment Advisers in International Financial Services Centre (IFSC)",
        "expected_category": "Investment Adviser",
        "date_hint": "2020-09-09"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/sep-2020/circular-on-tweaks-in-regulatory-framework-for-investment-advisers_47644.html",
        "title": "Circular on Guidelines for Investment Advisers",
        "expected_category": "Investment Adviser",
        "date_hint": "2020-09-23"
    },

    # -------------------------------------------------------------
    # 2. Mutual Funds (MF)
    # -------------------------------------------------------------
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jun-2024/master-circular-for-mutual-funds_84439.html",
        "title": "Master Circular for Mutual Funds",
        "expected_category": "Mutual Funds",
        "date_hint": "2024-06-27"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2024/framework-for-financial-disincentive-for-surveillance-related-lapses-at-amcs_83478.html",
        "title": "Framework for Financial Disincentive for Surveillance Related Lapses at AMCs",
        "expected_category": "Mutual Funds",
        "date_hint": "2024-05-21"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/apr-2024/framework-for-mutual-funds-for-investment-in-overseas-mutual-funds-unit-trusts_83060.html",
        "title": "Framework for Mutual Funds for Investment in Overseas Mutual Funds / Unit Trusts",
        "expected_category": "Mutual Funds",
        "date_hint": "2024-04-30"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/mar-2024/safeguards-to-address-the-concerns-of-investors-on-transfer-of-mutual-fund-units_82645.html",
        "title": "Safeguards to Address Concerns of Investors on Transfer of Mutual Fund Units",
        "expected_category": "Mutual Funds",
        "date_hint": "2024-03-28"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/nov-2023/simplification-of-framework-for-overseas-investment-by-mutual-funds_79255.html",
        "title": "Simplification of Framework for Overseas Investment by Mutual Funds",
        "expected_category": "Mutual Funds",
        "date_hint": "2023-11-20"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jul-2023/mandating-additional-disclosures-by-mutual-funds_74479.html",
        "title": "Mandating Additional Disclosures by Mutual Funds",
        "expected_category": "Mutual Funds",
        "date_hint": "2023-07-27"
    },

    # -------------------------------------------------------------
    # 3. Market Intermediaries & Stock Brokers
    # -------------------------------------------------------------
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2024/master-circular-for-stock-brokers_83552.html",
        "title": "Master Circular for Stock Brokers",
        "expected_category": "Market Intermediaries",
        "date_hint": "2024-05-22"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2024/master-circular-for-depositories_83554.html",
        "title": "Master Circular for Depositories",
        "expected_category": "Market Intermediaries",
        "date_hint": "2024-05-22"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jun-2024/streamlining-of-regulatory-reporting-by-designated-depository-participants-ddps-_84210.html",
        "title": "Streamlining of Regulatory Reporting by Designated Depository Participants (DDPs)",
        "expected_category": "Market Intermediaries",
        "date_hint": "2024-06-19"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/apr-2024/standard-operating-procedure-for-inter-operable-regulatory-sandbox_82811.html",
        "title": "Standard Operating Procedure for Inter-operable Regulatory Sandbox",
        "expected_category": "Market Intermediaries",
        "date_hint": "2024-04-12"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/mar-2024/measures-to-safeguard-investors-against-unauthorized-electronic-transfers_82201.html",
        "title": "Meeguards for Investors Against Unauthorized Electronic Transfers",
        "expected_category": "Market Intermediaries",
        "date_hint": "2024-03-11"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jan-2024/framework-for-kyc-registration-agencies-kras-_80750.html",
        "title": "Framework for KYC Registration Agencies (KRAs)",
        "expected_category": "Market Intermediaries",
        "date_hint": "2024-01-18"
    },

    # -------------------------------------------------------------
    # 4. Securities Markets / Listing Obligations (LODR / PIT / FPI)
    # -------------------------------------------------------------
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2024/master-circular-for-compliance-with-provisions-of-the-securities-and-exchange-board-of-india-listing-obligations-and-disclosure-requirements-regulations-2015-by-listed-entities_83551.html",
        "title": "Master Circular for Compliance with SEBI LODR Regulations by Listed Entities",
        "expected_category": "Securities Markets",
        "date_hint": "2024-05-21"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/mar-2024/introduction-of-beta-version-of-t-0-settlement_82412.html",
        "title": "Introduction of Beta Version of Optional T+0 Settlement for Equity Cash Markets",
        "expected_category": "Securities Markets",
        "date_hint": "2024-03-21"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/aug-2023/mandating-additional-disclosures-by-foreign-portfolio-investors-fpis-_76012.html",
        "title": "Mandating Additional Disclosures by Foreign Portfolio Investors (FPIs)",
        "expected_category": "Securities Markets",
        "date_hint": "2023-08-24"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jul-2023/disclosure-of-material-events-or-information-by-listed-entities_73921.html",
        "title": "Disclosure of Material Events or Information by Listed Entities under Regulation 30 of LODR",
        "expected_category": "Securities Markets",
        "date_hint": "2023-07-13"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jan-2024/framework-for-offer-for-sale-ofs-of-shares_80501.html",
        "title": "Comprehensive Framework for Offer for Sale (OFS) of Shares through Stock Exchange",
        "expected_category": "Securities Markets",
        "date_hint": "2024-01-05"
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/oct-2023/streamlining-the-process-of-public-issues-of-debt-securities_78110.html",
        "title": "Streamlining the Process of Public Issues of Debt Securities",
        "expected_category": "Securities Markets",
        "date_hint": "2023-10-16"
    }
]

# Helper function to get flat list of URLs
def get_seed_urls() -> List[str]:
    """Returns the list of document URLs for seed ingestion."""
    return [item["url"] for item in SEBI_DOCUMENT_URLS]
