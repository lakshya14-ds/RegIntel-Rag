"""
RegIntel RAG - Complete Technical Architecture & Codebase Audit Generator.
Generates:
  1. docs/RegIntel_RAG_Complete_Codebase_Audit.md
  2. docs/RegIntel_RAG_Complete_Codebase_Audit.pdf
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# ReportLab Imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
MD_PATH = DOCS_DIR / "RegIntel_RAG_Complete_Codebase_Audit.md"
PDF_PATH = DOCS_DIR / "RegIntel_RAG_Complete_Codebase_Audit.pdf"

print("Building RegIntel RAG Complete Codebase Audit...")

