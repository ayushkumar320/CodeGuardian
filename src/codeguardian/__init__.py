"""CodeGuardian AI — GitHub-native pre-merge risk checker.

Phase 1: deterministic PR analysis orchestrated by LangGraph, publishing a
``CodeGuardian Risk`` check, a sticky PR comment, and report artifacts.
"""

__version__ = "0.1.0"
ANALYZER_VERSION = "1"
SCHEMA_VERSION = "1"
SUMMARY_ANCHOR = "<!-- codeguardian-ai-summary -->"
CHECK_NAME = "CodeGuardian Risk"
