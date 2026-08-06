"""Optimización y reducción de redundancias."""
from __future__ import annotations

import re
from typing import Optional

from .audit import AuditEventType, PromptAuditTrail
from .common import normalize_text
from .advanced_common import _key
from .contracts import ResearchPromptValidator
from .models import PromptPackage

class PromptOptimizer:
    def optimize_text(self, text: str) -> str:
        text = normalize_text(text)
        if not text:
            return ""
        paragraphs = re.split(r"\n\s*\n", text)
        seen: set[str] = set()
        output: list[str] = []
        for paragraph in paragraphs:
            token = _key(re.sub(r"^#{1,6}\s+", "", paragraph))
            if token and token not in seen:
                seen.add(token)
                output.append(paragraph.strip())
        return re.sub(r"\n{3,}", "\n\n", "\n\n".join(output)).strip()

    def optimize_package(self, package: PromptPackage, *, audit_trail: Optional[PromptAuditTrail] = None) -> PromptPackage:
        ResearchPromptValidator.validate_package(package)
        before = package.to_dict()
        old_chars = package.total_characters
        package.system_prompt = self.optimize_text(package.system_prompt)
        package.developer_prompt = self.optimize_text(package.developer_prompt)
        package.user_prompt = self.optimize_text(package.user_prompt)
        saved = max(0, old_chars - package.total_characters)
        package.metadata["optimization"] = {
            "before_characters": old_chars,
            "after_characters": package.total_characters,
            "saved_characters": saved,
            "saved_percent": round(saved / old_chars * 100, 2) if old_chars else 0.0,
        }
        ResearchPromptValidator.validate_package(package)
        if audit_trail:
            audit_trail.add(AuditEventType.OPTIMIZED, "Paquete optimizado.", before=before,
                            after=package.to_dict(), details=package.metadata["optimization"])
        return package


