#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RAS Windows Path and Runtime Compatibility Fix

Corrects:
- AUD-005 Windows 8.3/long-path mismatch.
- AUD-009 Windows 8.3/long-path mismatch.
- AUD-006 _scan_packages staticmethod/signature mismatch.

Safety:
- Creates timestamped backups.
- Validates Python syntax before writing.
- Runs affected smoke tests.
- Runs the complete RAS integration test.
- Runs the complete RAS validator.
- Rolls back all modified files if any verification fails.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CONFIGURATION_SCANNER = ROOT / "configuration_scanner.py"
TEST_SCANNER = ROOT / "test_inventory_scanner.py"
RUNTIME_SCANNER = ROOT / "runtime_scanner.py"

TARGETS = (
    CONFIGURATION_SCANNER,
    TEST_SCANNER,
    RUNTIME_SCANNER,
)

HELPER_MARKER = "RAS WINDOWS PATH NORMALIZATION"

PATH_HELPER = r