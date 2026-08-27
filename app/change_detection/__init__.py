"""
Regulatory Change Detection Package for RegIntel RAG.
Provides predecessor matching, section alignment, and structured 'What Changed?' analysis.
"""

from app.change_detection.detector import RegulatoryChangeDetector, ChangeReport, SectionChange

__all__ = ["RegulatoryChangeDetector", "ChangeReport", "SectionChange"]
