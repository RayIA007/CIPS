#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTRL-018 Part II
Automatic installer

This installer prepares StageResult for the new consistency
architecture without changing validator behavior.

Actions
-------
- Creates timestamped backup.
- Verifies validate_project_control.py exists.
- Confirms CTRL-018 Part I is installed.
- Detects duplicate installation.
- Inserts compatibility marker for Part II.
- Verifies Python syntax.
- Rolls back automatically on failure.
"""

from __future__ import annotations
import ast
import shutil
from datetime import datetime
from pathlib import Path
import sys

TARGET="validate_project_control.py"
MARKER_I="CTRL-018 — VALIDATOR RESULT CONSISTENCY REFACTOR"
MARKER_II="CTRL-018 — PART II — STAGERESULT CONSISTENCY"

INJECTION = 