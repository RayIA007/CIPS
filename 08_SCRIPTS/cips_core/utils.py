from __future__ import annotations
from datetime import datetime, timezone
import uuid

def utc_now_iso(): return datetime.now(timezone.utc).isoformat()
def generate_id(prefix): return f"{prefix}_{uuid.uuid4().hex[:16]}"
