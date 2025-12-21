"""Local Claude analyzer used for multi-database transcript routing."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from anthropic import Anthropic

from src.config import Config

logger = logging.getLogger("Jarvis.LLM.Multi")


class ClaudeMultiAnalyzer:
    """Analyze transcripts for meetings, journals, reflections, tasks, and CRM."""

    VALID_PRIMARY_CATEGORIES = {
        "meeting",
        "reflection",
        "journal",
        "task_planning",
        "other",
    }

    def __init__(self, api_key: str, model: Optional[str] = None) -> None:
        self.client = Anthropic(api_key=api_key)

        primary_model = model or Config.CLAUDE_MODEL_PRIMARY
        fallback_models: List[str] = []
        for candidate in Config.CLAUDE_MODEL_OPTIONS:
            if candidate and candidate not in fallback_models and candidate != primary_model:
                fallback_models.append(candidate)

        self.model_primary = primary_model
        self.model_candidates = [primary_model] + fallback_models
        self.model = primary_model

        logger.info(
            "Claude Multi-Database analyzer initialized with models: %s",
            ", ".join(self.model_candidates),
        )

    def analyze_transcript(
        self,
        transcript: str,
        filename: str,
        recording_date: Optional[str] = None,
        existing_topics: Optional[List[Dict[str, str]]] = None,
    ) -> Dict:
        """Analyze transcript text and return structured routing guidance."""

        try:
            logger.info("Analyzing transcript for multi-database routing")

            if not recording_date:
                recording_date = datetime.now().date().isoformat()

            prompt = self._build_multi_analysis_prompt(
                transcript=transcript,
                filename=filename,
                recording_date=recording_date,
                """Deprecated analyzer stub kept only for backwards compatibility.

                The Jarvis architecture requires all LLM logic to live inside the
                jarvis-intelligence-service. This module used to host a local Claude
                analyzer but now intentionally fails on use to highlight the new
                contract.
                """

                from __future__ import annotations

                from typing import Dict


                class ClaudeMultiAnalyzer:  # pragma: no cover - safety net only
                    """Placeholder class that directs callers to the intelligence service."""

                    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - simple guard
                        raise RuntimeError(
                            "ClaudeMultiAnalyzer has been removed from jarvis-audio-pipeline. "
                            "Send transcripts to jarvis-intelligence-service /api/v1/process instead."
                        )

                    def analyze_transcript(self, *args, **kwargs) -> Dict:
                        raise RuntimeError(
                            "Local transcript analysis is disabled. Use jarvis-intelligence-service."
                        )

