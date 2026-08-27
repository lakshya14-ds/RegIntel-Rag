import re
from bs4 import BeautifulSoup


# Common web boilerplate/navigation noise patterns found in SEBI/financial portals
BOILERPLATE_PATTERNS = [
    r"(?i)skip to (?:main )?content",
    r"(?i)screen reader access",
    r"(?i)increase font size|decrease font size|normal font size",
    r"(?i)switch to dark mode|switch to light mode",
    r"(?i)share on (?:facebook|twitter|x|linkedin|whatsapp)",
    r"(?i)print this page|email this page",
    r"(?i)all rights reserved\b.*?(?:sebi|moneycontrol)?",
    r"(?i)copyright\s*(?:©|\(c\))\s*\d{4}.*?(?:sebi|moneycontrol)?",
    r"(?i)cookie policy|privacy policy|terms of use",
    r"(?i)terms & conditions|website policy|privacy policy",
    r"(?i)the site is best viewed in.*",
    r"(?i)gst no\..*",
    r"(?i)click here to make payment.*",
]

# Section headers representing navigation trees rather than document content
NAVIGATION_HEADERS = [
    r"(?i)^#+\s*(?:info for|departments & divisions|investor complaints|what's new|follow us|video|preamble of the securities and exchange board of india)$",
    r"(?i)^#+\s*सेबी की वेबसाइट पर आपका स्वागत है.*",
]


def clean_html(html_content: str) -> str:
    """Cleans HTML content by removing scripts, styles, and navigational elements, preserving text."""
    if not html_content or not isinstance(html_content, str):
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    return clean_markdown(text)


def clean_markdown(text: str) -> str:
    """
    Cleans and normalizes markdown/extracted text while preserving regulatory structure.
    - Preserves headings (#, ##, etc.)
    - Preserves numbered/alphabetical list items (1., 1.1, (a), (i), etc.)
    - Preserves tables and structured clauses
    - Normalizes line breaks and whitespace
    - Filters out obvious navigation noise
    """
    if not text or not isinstance(text, str):
        return ""

    # Normalize carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Filter boilerplate noise line by line
    cleaned_lines = []
    skip_navigation_block = False

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        # Check if line starts a pure navigation section (e.g. ## Departments & Divisions)
        is_nav_header = False
        for nav_h in NAVIGATION_HEADERS:
            if re.match(nav_h, stripped):
                is_nav_header = True
                break

        if is_nav_header:
            skip_navigation_block = True
            continue

        # If we hit a new real section that isn't navigation, exit skip block
        if skip_navigation_block and re.match(r"^#{1,3}\s+[A-Z0-9]", stripped):
            skip_navigation_block = False

        if skip_navigation_block:
            continue

        # Check if line matches boilerplate pattern
        is_boilerplate = False
        for pattern in BOILERPLATE_PATTERNS:
            if re.fullmatch(pattern, stripped) or re.search(pattern, stripped):
                is_boilerplate = True
                break

        if not is_boilerplate:
            # Normalize internal inline spaces (tabs, multiple spaces) while preserving indentation for lists
            normalized_line = re.sub(r"[ \t]+", " ", line)
            cleaned_lines.append(normalized_line)

    text = "\n".join(cleaned_lines)

    # Normalize excessive consecutive blank lines (limit to max 2 consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


class TextCleaner:
    """Compatibility wrapper for clean_markdown and clean_html."""
    @staticmethod
    def clean_text(text: str) -> str:
        return clean_markdown(text)

    @staticmethod
    def clean_html(html: str) -> str:
        return clean_html(html)
