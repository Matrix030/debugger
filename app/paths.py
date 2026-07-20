# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Canonical filesystem paths for DebugLab data and assets."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
QUESTIONS_DIR = DATA_DIR / "questions"
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
