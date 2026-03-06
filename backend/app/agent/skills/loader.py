"""Skill loader — discovers and loads skill definitions for the agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SkillLoader:
    """Discovers and loads skills from the skills directory.

    Each skill is a directory containing at minimum a SKILL.md file.
    Optionally, it may contain:
    - controls.json — machine-readable control definitions
    - evidence-map.json — control → evidence source mapping
    - rego-examples/ — reference Rego policies
    """

    def __init__(self, base_path: str = "skills") -> None:
        self._base = Path(base_path)
        self._cache: dict[str, dict[str, Any]] = {}

    def discover(self) -> list[dict[str, Any]]:
        """Discover all available skills."""
        skills = []
        if not self._base.exists():
            logger.warning("skills_dir_missing", path=str(self._base))
            return skills

        for entry in sorted(self._base.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue

            skill_info: dict[str, Any] = {
                "id": entry.name,
                "path": str(entry),
                "has_controls": (entry / "controls.json").exists(),
                "has_evidence_map": (entry / "evidence-map.json").exists(),
                "has_rego_examples": (entry / "rego-examples").is_dir(),
            }
            skills.append(skill_info)
            logger.debug("skill_discovered", skill=entry.name)

        return skills

    def load_skill_content(self, skill_id: str) -> str:
        """Load the SKILL.md content for a given skill."""
        if skill_id in self._cache and "content" in self._cache[skill_id]:
            return self._cache[skill_id]["content"]

        skill_path = self._base / skill_id / "SKILL.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill not found: {skill_id}")

        content = skill_path.read_text(encoding="utf-8")
        self._cache.setdefault(skill_id, {})["content"] = content
        return content

    def load_controls(self, skill_id: str) -> dict[str, Any]:
        """Load controls.json for a compliance framework skill."""
        if skill_id in self._cache and "controls" in self._cache[skill_id]:
            return self._cache[skill_id]["controls"]

        controls_path = self._base / skill_id / "controls.json"
        if not controls_path.exists():
            raise FileNotFoundError(f"Controls file not found for skill: {skill_id}")

        data = json.loads(controls_path.read_text(encoding="utf-8"))
        self._cache.setdefault(skill_id, {})["controls"] = data
        return data

    def load_evidence_map(self, skill_id: str) -> dict[str, Any]:
        """Load evidence-map.json for a compliance framework skill."""
        map_path = self._base / skill_id / "evidence-map.json"
        if not map_path.exists():
            return {}

        return json.loads(map_path.read_text(encoding="utf-8"))

    def load_rego_examples(self, skill_id: str) -> list[dict[str, str]]:
        """Load all Rego example files from a skill's rego-examples/ directory."""
        examples_dir = self._base / skill_id / "rego-examples"
        if not examples_dir.is_dir():
            return []

        examples = []
        for rego_file in sorted(examples_dir.glob("*.rego")):
            examples.append({
                "filename": rego_file.name,
                "content": rego_file.read_text(encoding="utf-8"),
            })
        return examples

    def clear_cache(self) -> None:
        """Clear the skill cache."""
        self._cache.clear()
