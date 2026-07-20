# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question bank: YAML schema, validation, and cached loading.

Questions live as hand-editable YAML files under ``data/questions/``.
Files are loaded in filename order (use numeric prefixes such as
``001_...yaml`` to control ordering). ``example.yaml`` is always skipped
so the authoring template never appears as a real question.
"""

import ast
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from app.paths import QUESTIONS_DIR

TEMPLATE_FILENAME = "example.yaml"
_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class QuestionValidationError(ValueError):
    """Raised when a question file fails schema validation."""


class TestCase(BaseModel):
    """A single test: call the target function with ``args``, expect ``expected``."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    args: list[Any]
    expected: Any = None


class Question(BaseModel):
    """Full server-side question definition (includes hidden/interviewer data)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    category: str = Field(default="General", min_length=1)
    tags: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    function_name: str
    language: Literal["python"] = "python"
    starter_code: str = Field(min_length=1)
    visible_tests: list[TestCase] = Field(min_length=1)
    hidden_tests: list[TestCase] = Field(min_length=1)
    interviewer_notes: str = ""
    solution: str = Field(min_length=1)
    time_limit_seconds: int = Field(default=5, ge=1, le=30)
    memory_limit_mb: int = Field(default=256, ge=64, le=1024)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _ID_PATTERN.match(value):
            raise ValueError(
                f"question id {value!r} must be a lowercase kebab-case slug"
            )
        return value

    @field_validator("function_name")
    @classmethod
    def _validate_function_name(cls, value: str) -> str:
        if not value.isidentifier():
            raise ValueError(f"function_name {value!r} is not a valid identifier")
        return value

    @model_validator(mode="after")
    def _validate_function_defined(self) -> "Question":
        for label, source in (
            ("starter_code", self.starter_code),
            ("solution", self.solution),
        ):
            if self.function_name not in _top_level_functions(source, label):
                raise ValueError(
                    f"{label} must define top-level function "
                    f"{self.function_name!r} (question {self.id!r})"
                )
        return self


def _top_level_functions(source: str, label: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"{label} is not valid Python: {exc.msg}") from exc
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def load_question_file(path: Path) -> Question:
    """Load and validate a single question YAML file."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise QuestionValidationError(f"{path.name}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise QuestionValidationError(f"{path.name}: expected a YAML mapping")
    try:
        return Question.model_validate(raw)
    except ValueError as exc:
        raise QuestionValidationError(f"{path.name}: {exc}") from exc


class QuestionBank:
    """Loads questions from a directory with an mtime-based cache.

    Hand edits to YAML files show up on the next request without an
    application restart.
    """

    def __init__(self, directory: Path = QUESTIONS_DIR) -> None:
        self._directory = directory
        self._cache_key: tuple[tuple[str, float], ...] | None = None
        self._questions: list[Question] = []
        self._by_id: dict[str, Question] = {}

    def _question_files(self) -> list[Path]:
        if not self._directory.is_dir():
            return []
        return sorted(
            path
            for path in self._directory.glob("*.yaml")
            if path.name != TEMPLATE_FILENAME
        )

    def _refresh(self) -> None:
        files = self._question_files()
        cache_key = tuple((path.name, path.stat().st_mtime) for path in files)
        if cache_key == self._cache_key:
            return
        questions: list[Question] = []
        by_id: dict[str, Question] = {}
        for path in files:
            question = load_question_file(path)
            if question.id in by_id:
                raise QuestionValidationError(
                    f"{path.name}: duplicate question id {question.id!r}"
                )
            questions.append(question)
            by_id[question.id] = question
        self._cache_key = cache_key
        self._questions = questions
        self._by_id = by_id

    def all(self) -> list[Question]:
        """Return every question in display order."""
        self._refresh()
        return list(self._questions)

    def get(self, question_id: str) -> Question | None:
        """Return one question by id, or ``None`` if unknown."""
        self._refresh()
        return self._by_id.get(question_id)

    def index_of(self, question_id: str) -> int:
        """Return the zero-based position of a question, or ``-1``."""
        self._refresh()
        for index, question in enumerate(self._questions):
            if question.id == question_id:
                return index
        return -1


question_bank = QuestionBank()
