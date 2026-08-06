#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CTRL-018 — Validator Result Consistency Refactor
Integrated automatic installer

This installer applies the complete consistency refactor as one
transaction. It is designed to replace the failed incremental Part II
approach.

Safety
------
- Modifies only validate_project_control.py.
- Installs Part I automatically when it is missing.
- Refuses duplicate integrated installation.
- Creates a timestamped backup.
- Validates syntax before and after writing.
- Executes an isolated consistency regression test.
- Restores the backup automatically on any failure.
- Modifies no YAML or Markdown files.
"""

from __future__ import annotations

import ast
import base64
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


TARGET_NAME = "validate_project_control.py"

PART_I_MARKER = (
    "CTRL-018 — VALIDATOR RESULT CONSISTENCY REFACTOR"
)
INTEGRATED_MARKER = (
    "CTRL-018 — VALIDATOR RESULT CONSISTENCY REFACTOR\n"
    "# INTEGRATED CONSISTENCY SUPPORT"
)
STAGE_CONTRACT_MARKER = """# =============================================================================
# VALIDATION STAGE CONTRACT
# =============================================================================
"""

PART_I_CODE = base64.b64decode(
    "IyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQojIENUUkwtMDE4IOKAlCBWQUxJREFUT1IgUkVTVUxUIENPTlNJU1RFTkNZIFJFRkFDVE9SCiMgUEFSVCBJIOKAlCBSRVNVTFQgTk9STUFMSVpBVElPTiBBUkNISVRFQ1RVUkUKIyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQojCiMgUGxhY2VtZW50OgojICAgSW5zZXJ0IHRoaXMgYmxvY2sgYWZ0ZXIgVmFsaWRhdGlvbkNvbnRleHQgYW5kIGJlZm9yZSB0aGUKIyAgICJWQUxJREFUSU9OIFNUQUdFIENPTlRSQUNUIiBzZWN0aW9uLgojCiMgUGFydCBJIGlzIGludGVudGlvbmFsbHkgbm9uLWludmFzaXZlOgojICAgLSBpdCBpbnRyb2R1Y2VzIHRoZSBuZXcgY29uc2lzdGVuY3kgYXJjaGl0ZWN0dXJlOwojICAgLSBpdCBkb2VzIG5vdCByZXBsYWNlIFN0YWdlUmVzdWx0IHlldDsKIyAgIC0gaXQgZG9lcyBub3QgYWx0ZXIgdGhlIHBpcGVsaW5lIHlldDsKIyAgIC0gaXQgZG9lcyBub3QgY2hhbmdlIENMSSBiZWhhdmlvciB5ZXQuCiMKIyBJbnRlZ3JhdGlvbiBvY2N1cnMgaW4gUGFydHMgSUnigJNWSUkuCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCgpjbGFzcyBGaW5kaW5nRGlzcG9zaXRpb24oc3RyLCBFbnVtKToKICAgICIiIgogICAgRGVjaXNpb24gcHJvZHVjZWQgYnkgYSBub3JtYWxpemF0aW9uIHJ1bGUgZm9yIG9uZSBmaW5kaW5nLgoKICAgIEtFRVA6CiAgICAgICAgUHJlc2VydmUgdGhlIGZpbmRpbmcgd2l0aG91dCBjaGFuZ2VzLgoKICAgIFJFTU9WRToKICAgICAgICBSZW1vdmUgYSBsZWdhY3kgb3IgY29udGV4dHVhbGx5IGludmFsaWQgZmluZGluZy4KCiAgICBSRVBMQUNFOgogICAgICAgIFJlcGxhY2UgdGhlIG9yaWdpbmFsIGZpbmRpbmcgd2l0aCBhIG5vcm1hbGl6ZWQgZmluZGluZy4KICAgICIiIgoKICAgIEtFRVAgPSAiS0VFUCIKICAgIFJFTU9WRSA9ICJSRU1PVkUiCiAgICBSRVBMQUNFID0gIlJFUExBQ0UiCgoKQGRhdGFjbGFzcyhmcm96ZW49VHJ1ZSwgc2xvdHM9VHJ1ZSkKY2xhc3MgRmluZGluZ0RlY2lzaW9uOgogICAgIiIiCiAgICBJbW11dGFibGUgZGVjaXNpb24gcmV0dXJuZWQgYnkgb25lIG5vcm1hbGl6YXRpb24gcnVsZS4KICAgICIiIgoKICAgIGRpc3Bvc2l0aW9uOiBGaW5kaW5nRGlzcG9zaXRpb24KICAgIHJlcGxhY2VtZW50OiBWYWxpZGF0aW9uRmluZGluZyB8IE5vbmUgPSBOb25lCiAgICByZWFzb246IHN0ciB8IE5vbmUgPSBOb25lCgogICAgZGVmIF9fcG9zdF9pbml0X18oc2VsZikgLT4gTm9uZToKICAgICAgICBpZiAoCiAgICAgICAgICAgIHNlbGYuZGlzcG9zaXRpb24gaXMgRmluZGluZ0Rpc3Bvc2l0aW9uLlJFUExBQ0UKICAgICAgICAgICAgYW5kIHNlbGYucmVwbGFjZW1lbnQgaXMgTm9uZQogICAgICAgICk6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICAgICAiUkVQTEFDRSBkZWNpc2lvbnMgcmVxdWlyZSBhIHJlcGxhY2VtZW50IGZpbmRpbmcuIgogICAgICAgICAgICApCgogICAgICAgIGlmICgKICAgICAgICAgICAgc2VsZi5kaXNwb3NpdGlvbiBpcyBub3QgRmluZGluZ0Rpc3Bvc2l0aW9uLlJFUExBQ0UKICAgICAgICAgICAgYW5kIHNlbGYucmVwbGFjZW1lbnQgaXMgbm90IE5vbmUKICAgICAgICApOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgIk9ubHkgUkVQTEFDRSBkZWNpc2lvbnMgbWF5IGluY2x1ZGUgYSByZXBsYWNlbWVudCBmaW5kaW5nLiIKICAgICAgICAgICAgKQoKICAgIEBjbGFzc21ldGhvZAogICAgZGVmIGtlZXAoCiAgICAgICAgY2xzLAogICAgICAgICosCiAgICAgICAgcmVhc29uOiBzdHIgfCBOb25lID0gTm9uZSwKICAgICkgLT4gIkZpbmRpbmdEZWNpc2lvbiI6CiAgICAgICAgcmV0dXJuIGNscygKICAgICAgICAgICAgZGlzcG9zaXRpb249RmluZGluZ0Rpc3Bvc2l0aW9uLktFRVAsCiAgICAgICAgICAgIHJlYXNvbj1yZWFzb24sCiAgICAgICAgKQoKICAgIEBjbGFzc21ldGhvZAogICAgZGVmIHJlbW92ZSgKICAgICAgICBjbHMsCiAgICAgICAgKiwKICAgICAgICByZWFzb246IHN0ciwKICAgICkgLT4gIkZpbmRpbmdEZWNpc2lvbiI6CiAgICAgICAgcmV0dXJuIGNscygKICAgICAgICAgICAgZGlzcG9zaXRpb249RmluZGluZ0Rpc3Bvc2l0aW9uLlJFTU9WRSwKICAgICAgICAgICAgcmVhc29uPXJlYXNvbiwKICAgICAgICApCgogICAgQGNsYXNzbWV0aG9kCiAgICBkZWYgcmVwbGFjZSgKICAgICAgICBjbHMsCiAgICAgICAgKiwKICAgICAgICByZXBsYWNlbWVudDogVmFsaWRhdGlvbkZpbmRpbmcsCiAgICAgICAgcmVhc29uOiBzdHIsCiAgICApIC0+ICJGaW5kaW5nRGVjaXNpb24iOgogICAgICAgIHJldHVybiBjbHMoCiAgICAgICAgICAgIGRpc3Bvc2l0aW9uPUZpbmRpbmdEaXNwb3NpdGlvbi5SRVBMQUNFLAogICAgICAgICAgICByZXBsYWNlbWVudD1yZXBsYWNlbWVudCwKICAgICAgICAgICAgcmVhc29uPXJlYXNvbiwKICAgICAgICApCgoKQGRhdGFjbGFzcyhmcm96ZW49VHJ1ZSwgc2xvdHM9VHJ1ZSkKY2xhc3MgUmVzdWx0Tm9ybWFsaXphdGlvbkNvbnRleHQ6CiAgICAiIiIKICAgIFJlYWQtb25seSBjb250ZXh0IHN1cHBsaWVkIHRvIGV2ZXJ5IHJlc3VsdC1ub3JtYWxpemF0aW9uIHJ1bGUuCgogICAgVGhlIGNsYXNzIHNlcGFyYXRlcyBub3JtYWxpemF0aW9uIGlucHV0cyBmcm9tIHRoZSBtdXRhYmxlIHZhbGlkYXRvcgogICAgZXhlY3V0aW9uIGNvbnRleHQuIFJ1bGVzIG1heSBpbnNwZWN0IHJlcG9zaXRvcnkgc3RhdGUgYnV0IG1heSBub3QKICAgIG1vZGlmeSBwcm9qZWN0IGRvY3VtZW50cy4KICAgICIiIgoKICAgIHZhbGlkYXRpb25fY29udGV4dDogVmFsaWRhdGlvbkNvbnRleHQKICAgIHN0YWdlOiBTdGFnZU5hbWUKICAgIG9yaWdpbmFsX2ZpbmRpbmdzOiB0dXBsZVtWYWxpZGF0aW9uRmluZGluZywgLi4uXQogICAgbWV0YWRhdGE6IE1hcHBpbmdbc3RyLCBBbnldCgogICAgQGNsYXNzbWV0aG9kCiAgICBkZWYgZnJvbV9zdGFnZSgKICAgICAgICBjbHMsCiAgICAgICAgKiwKICAgICAgICB2YWxpZGF0aW9uX2NvbnRleHQ6IFZhbGlkYXRpb25Db250ZXh0LAogICAgICAgIHN0YWdlX3Jlc3VsdDogU3RhZ2VSZXN1bHQsCiAgICApIC0+ICJSZXN1bHROb3JtYWxpemF0aW9uQ29udGV4dCI6CiAgICAgICAgcmV0dXJuIGNscygKICAgICAgICAgICAgdmFsaWRhdGlvbl9jb250ZXh0PXZhbGlkYXRpb25fY29udGV4dCwKICAgICAgICAgICAgc3RhZ2U9c3RhZ2VfcmVzdWx0LnN0YWdlLAogICAgICAgICAgICBvcmlnaW5hbF9maW5kaW5ncz10dXBsZShzdGFnZV9yZXN1bHQuZmluZGluZ3MpLAogICAgICAgICAgICBtZXRhZGF0YT1kaWN0KHZhbGlkYXRpb25fY29udGV4dC5tZXRhZGF0YSksCiAgICAgICAgKQoKCkBkYXRhY2xhc3MoZnJvemVuPVRydWUsIHNsb3RzPVRydWUpCmNsYXNzIEZpbmRpbmdOb3JtYWxpemF0aW9uUnVsZToKICAgICIiIgogICAgRGVjbGFyYXRpdmUgcnVsZSB1c2VkIGJ5IFJlc3VsdE5vcm1hbGl6ZXIuCgogICAgQSBydWxlIGlzIGV2YWx1YXRlZCBvbmx5IGZvciB0aGUgY29uZmlndXJlZCBzdGFnZXMgYW5kIGZpbmRpbmcgY29kZXMuCiAgICBUaGUgcHJlZGljYXRlIHJlY2VpdmVzIHRoZSBmaW5kaW5nIGFuZCB0aGUgaW1tdXRhYmxlIG5vcm1hbGl6YXRpb24KICAgIGNvbnRleHQuIEl0IG11c3QgcmV0dXJuIFRydWUgb25seSB3aGVuIHRoZSBydWxlIGlzIGFwcGxpY2FibGUuCiAgICAiIiIKCiAgICBydWxlX2lkOiBzdHIKICAgIHN0YWdlczogZnJvemVuc2V0W1N0YWdlTmFtZV0KICAgIGZpbmRpbmdfY29kZXM6IGZyb3plbnNldFtzdHJdCiAgICBwcmVkaWNhdGU6IENhbGxhYmxlWwogICAgICAgIFtWYWxpZGF0aW9uRmluZGluZywgUmVzdWx0Tm9ybWFsaXphdGlvbkNvbnRleHRdLAogICAgICAgIGJvb2wsCiAgICBdCiAgICBkZWNpc2lvbl9mYWN0b3J5OiBDYWxsYWJsZVsKICAgICAgICBbVmFsaWRhdGlvbkZpbmRpbmcsIFJlc3VsdE5vcm1hbGl6YXRpb25Db250ZXh0XSwKICAgICAgICBGaW5kaW5nRGVjaXNpb24sCiAgICBdCiAgICBwcmlvcml0eTogaW50ID0gMTAwCgogICAgZGVmIGFwcGxpZXNfdG8oCiAgICAgICAgc2VsZiwKICAgICAgICAqLAogICAgICAgIGZpbmRpbmc6IFZhbGlkYXRpb25GaW5kaW5nLAogICAgICAgIGNvbnRleHQ6IFJlc3VsdE5vcm1hbGl6YXRpb25Db250ZXh0LAogICAgKSAtPiBib29sOgogICAgICAgIGlmIGNvbnRleHQuc3RhZ2Ugbm90IGluIHNlbGYuc3RhZ2VzOgogICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgaWYgKAogICAgICAgICAgICBzZWxmLmZpbmRpbmdfY29kZXMKICAgICAgICAgICAgYW5kIGZpbmRpbmcuY29kZSBub3QgaW4gc2VsZi5maW5kaW5nX2NvZGVzCiAgICAgICAgKToKICAgICAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgICAgIHJldHVybiBib29sKAogICAgICAgICAgICBzZWxmLnByZWRpY2F0ZSgKICAgICAgICAgICAgICAgIGZpbmRpbmcsCiAgICAgICAgICAgICAgICBjb250ZXh0LAogICAgICAgICAgICApCiAgICAgICAgKQoKCkBkYXRhY2xhc3MoZnJvemVuPVRydWUsIHNsb3RzPVRydWUpCmNsYXNzIE5vcm1hbGl6YXRpb25BdWRpdFJlY29yZDoKICAgICIiIgogICAgT25lIGF1ZGl0YWJsZSBkZWNpc2lvbiBwcm9kdWNlZCBkdXJpbmcgbm9ybWFsaXphdGlvbi4KICAgICIiIgoKICAgIHJ1bGVfaWQ6IHN0cgogICAgc3RhZ2U6IFN0YWdlTmFtZQogICAgZmluZGluZ19jb2RlOiBzdHIKICAgIGRpc3Bvc2l0aW9uOiBGaW5kaW5nRGlzcG9zaXRpb24KICAgIHJlYXNvbjogc3RyIHwgTm9uZSA9IE5vbmUKCgpAZGF0YWNsYXNzKGZyb3plbj1UcnVlLCBzbG90cz1UcnVlKQpjbGFzcyBOb3JtYWxpemVkU3RhZ2VTbmFwc2hvdDoKICAgICIiIgogICAgSW1tdXRhYmxlIG5vcm1hbGl6ZWQgcmVwcmVzZW50YXRpb24gb2Ygb25lIHZhbGlkYXRpb24gc3RhZ2UuCgogICAgVGhpcyBzbmFwc2hvdCBpcyB0aGUgY2Fub25pY2FsIGlucHV0IGZvciBzdGF0dXMgYWdncmVnYXRpb24uIEl0CiAgICBwcmV2ZW50cyByZXBvcnQgcmVuZGVyaW5nIGFuZCBleGl0LWNvZGUgcmVzb2x1dGlvbiBmcm9tIHJlYWRpbmcKICAgIHN0YWxlIFN0YWdlUmVzdWx0LnN0YXR1cyB2YWx1ZXMuCiAgICAiIiIKCiAgICBzdGFnZTogU3RhZ2VOYW1lCiAgICBmaW5kaW5nczogdHVwbGVbVmFsaWRhdGlvbkZpbmRpbmcsIC4uLl0KICAgIGNoZWNrc19leGVjdXRlZDogaW50CiAgICBzdGFydGVkX2F0OiBkYXRldGltZSB8IE5vbmUKICAgIGZpbmlzaGVkX2F0OiBkYXRldGltZSB8IE5vbmUKICAgIGR1cmF0aW9uX3NlY29uZHM6IGZsb2F0CiAgICBzdGF0dXM6IFZhbGlkYXRpb25TdGF0dXMKICAgIGF1ZGl0OiB0dXBsZVtOb3JtYWxpemF0aW9uQXVkaXRSZWNvcmQsIC4uLl0gPSAoKQoKICAgIEBwcm9wZXJ0eQogICAgZGVmIGVycm9ycyhzZWxmKSAtPiBpbnQ6CiAgICAgICAgcmV0dXJuIHN1bSgKICAgICAgICAgICAgZmluZGluZy5zZXZlcml0eSBpcyBWYWxpZGF0aW9uU2V2ZXJpdHkuRVJST1IKICAgICAgICAgICAgZm9yIGZpbmRpbmcgaW4gc2VsZi5maW5kaW5ncwogICAgICAgICkKCiAgICBAcHJvcGVydHkKICAgIGRlZiBjcml0aWNhbF9lcnJvcnMoc2VsZikgLT4gaW50OgogICAgICAgIHJldHVybiBzdW0oCiAgICAgICAgICAgIGZpbmRpbmcuc2V2ZXJpdHkgaXMgVmFsaWRhdGlvblNldmVyaXR5LkNSSVRJQ0FMCiAgICAgICAgICAgIGZvciBmaW5kaW5nIGluIHNlbGYuZmluZGluZ3MKICAgICAgICApCgogICAgQHByb3BlcnR5CiAgICBkZWYgd2FybmluZ3Moc2VsZikgLT4gaW50OgogICAgICAgIHJldHVybiBzdW0oCiAgICAgICAgICAgIGZpbmRpbmcuc2V2ZXJpdHkgaXMgVmFsaWRhdGlvblNldmVyaXR5LldBUk5JTkcKICAgICAgICAgICAgZm9yIGZpbmRpbmcgaW4gc2VsZi5maW5kaW5ncwogICAgICAgICkKCiAgICBAcHJvcGVydHkKICAgIGRlZiBpbmZvcm1hdGlvbihzZWxmKSAtPiBpbnQ6CiAgICAgICAgcmV0dXJuIHN1bSgKICAgICAgICAgICAgZmluZGluZy5zZXZlcml0eSBpcyBWYWxpZGF0aW9uU2V2ZXJpdHkuSU5GTwogICAgICAgICAgICBmb3IgZmluZGluZyBpbiBzZWxmLmZpbmRpbmdzCiAgICAgICAgKQoKICAgIEBwcm9wZXJ0eQogICAgZGVmIHBhc3NlZChzZWxmKSAtPiBib29sOgogICAgICAgIHJldHVybiBzZWxmLnN0YXR1cyBpbiB7CiAgICAgICAgICAgIFZhbGlkYXRpb25TdGF0dXMuUEFTUywKICAgICAgICAgICAgVmFsaWRhdGlvblN0YXR1cy5XQVJOSU5HLAogICAgICAgIH0KCgpjbGFzcyBTdGF0dXNSZXNvbHZlcjoKICAgICIiIgogICAgU2luZ2xlIGF1dGhvcml0eSBmb3IgU3RhZ2VSZXN1bHQgYW5kIFZhbGlkYXRpb25SZXBvcnQgc3RhdHVzLgoKICAgIE5vIGNhbGxlciBzaG91bGQgaW5mZXIgUEFTUyBvciBGQUlMIGluZGVwZW5kZW50bHkgZnJvbSBjYWNoZWQgZmxhZ3MuCiAgICAiIiIKCiAgICBAc3RhdGljbWV0aG9kCiAgICBkZWYgcmVzb2x2ZV9maW5kaW5ncygKICAgICAgICBmaW5kaW5nczogSXRlcmFibGVbVmFsaWRhdGlvbkZpbmRpbmddLAogICAgKSAtPiBWYWxpZGF0aW9uU3RhdHVzOgogICAgICAgIG5vcm1hbGl6ZWQgPSB0dXBsZShmaW5kaW5ncykKCiAgICAgICAgaWYgYW55KAogICAgICAgICAgICBmaW5kaW5nLnNldmVyaXR5IGlzIFZhbGlkYXRpb25TZXZlcml0eS5DUklUSUNBTAogICAgICAgICAgICBmb3IgZmluZGluZyBpbiBub3JtYWxpemVkCiAgICAgICAgKToKICAgICAgICAgICAgcmV0dXJuIFZhbGlkYXRpb25TdGF0dXMuRkFJTAoKICAgICAgICBpZiBhbnkoCiAgICAgICAgICAgIGZpbmRpbmcuc2V2ZXJpdHkgaXMgVmFsaWRhdGlvblNldmVyaXR5LkVSUk9SCiAgICAgICAgICAgIGZvciBmaW5kaW5nIGluIG5vcm1hbGl6ZWQKICAgICAgICApOgogICAgICAgICAgICByZXR1cm4gVmFsaWRhdGlvblN0YXR1cy5GQUlMCgogICAgICAgIGlmIGFueSgKICAgICAgICAgICAgZmluZGluZy5zZXZlcml0eSBpcyBWYWxpZGF0aW9uU2V2ZXJpdHkuV0FSTklORwogICAgICAgICAgICBmb3IgZmluZGluZyBpbiBub3JtYWxpemVkCiAgICAgICAgKToKICAgICAgICAgICAgcmV0dXJuIFZhbGlkYXRpb25TdGF0dXMuV0FSTklORwoKICAgICAgICByZXR1cm4gVmFsaWRhdGlvblN0YXR1cy5QQVNTCgogICAgQGNsYXNzbWV0aG9kCiAgICBkZWYgcmVzb2x2ZV9zdGFnZSgKICAgICAgICBjbHMsCiAgICAgICAgc3RhZ2VfcmVzdWx0OiBTdGFnZVJlc3VsdCwKICAgICkgLT4gVmFsaWRhdGlvblN0YXR1czoKICAgICAgICByZXR1cm4gY2xzLnJlc29sdmVfZmluZGluZ3MoCiAgICAgICAgICAgIHN0YWdlX3Jlc3VsdC5maW5kaW5ncwogICAgICAgICkKCiAgICBAc3RhdGljbWV0aG9kCiAgICBkZWYgcmVzb2x2ZV9yZXBvcnQoCiAgICAgICAgc3RhZ2VzOiBJdGVyYWJsZVsKICAgICAgICAgICAgU3RhZ2VSZXN1bHQgfCBOb3JtYWxpemVkU3RhZ2VTbmFwc2hvdAogICAgICAgIF0sCiAgICApIC0+IFZhbGlkYXRpb25TdGF0dXM6CiAgICAgICAgbm9ybWFsaXplZF9zdGFnZXMgPSB0dXBsZShzdGFnZXMpCgogICAgICAgIGlmIG5vdCBub3JtYWxpemVkX3N0YWdlczoKICAgICAgICAgICAgcmV0dXJuIFZhbGlkYXRpb25TdGF0dXMuU0tJUFBFRAoKICAgICAgICBzdGF0dXNlcyA9IHR1cGxlKAogICAgICAgICAgICAoCiAgICAgICAgICAgICAgICBzdGFnZS5zdGF0dXMKICAgICAgICAgICAgICAgIGlmIGlzaW5zdGFuY2UoCiAgICAgICAgICAgICAgICAgICAgc3RhZ2UsCiAgICAgICAgICAgICAgICAgICAgTm9ybWFsaXplZFN0YWdlU25hcHNob3QsCiAgICAgICAgICAgICAgICApCiAgICAgICAgICAgICAgICBlbHNlIFN0YXR1c1Jlc29sdmVyLnJlc29sdmVfc3RhZ2Uoc3RhZ2UpCiAgICAgICAgICAgICkKICAgICAgICAgICAgZm9yIHN0YWdlIGluIG5vcm1hbGl6ZWRfc3RhZ2VzCiAgICAgICAgKQoKICAgICAgICBpZiBhbnkoCiAgICAgICAgICAgIHN0YXR1cyBpcyBWYWxpZGF0aW9uU3RhdHVzLkZBSUwKICAgICAgICAgICAgZm9yIHN0YXR1cyBpbiBzdGF0dXNlcwogICAgICAgICk6CiAgICAgICAgICAgIHJldHVybiBWYWxpZGF0aW9uU3RhdHVzLkZBSUwKCiAgICAgICAgaWYgYW55KAogICAgICAgICAgICBzdGF0dXMgaXMgVmFsaWRhdGlvblN0YXR1cy5XQVJOSU5HCiAgICAgICAgICAgIGZvciBzdGF0dXMgaW4gc3RhdHVzZXMKICAgICAgICApOgogICAgICAgICAgICByZXR1cm4gVmFsaWRhdGlvblN0YXR1cy5XQVJOSU5HCgogICAgICAgIGlmIGFsbCgKICAgICAgICAgICAgc3RhdHVzIGlzIFZhbGlkYXRpb25TdGF0dXMuU0tJUFBFRAogICAgICAgICAgICBmb3Igc3RhdHVzIGluIHN0YXR1c2VzCiAgICAgICAgKToKICAgICAgICAgICAgcmV0dXJuIFZhbGlkYXRpb25TdGF0dXMuU0tJUFBFRAoKICAgICAgICByZXR1cm4gVmFsaWRhdGlvblN0YXR1cy5QQVNTCgogICAgQGNsYXNzbWV0aG9kCiAgICBkZWYgc3luY2hyb25pemVfc3RhZ2Vfc3RhdHVzKAogICAgICAgIGNscywKICAgICAgICBzdGFnZV9yZXN1bHQ6IFN0YWdlUmVzdWx0LAogICAgKSAtPiBWYWxpZGF0aW9uU3RhdHVzOgogICAgICAgICIiIgogICAgICAgIFJlY2FsY3VsYXRlIGFuZCB3cml0ZSB0aGUgY2Fub25pY2FsIHN0YXR1cyBpbnRvIFN0YWdlUmVzdWx0LgoKICAgICAgICBUaGlzIGNvbXBhdGliaWxpdHkgbWV0aG9kIGlzIHRlbXBvcmFyeS4gUGFydCBJSSB3aWxsIHJlcGxhY2UKICAgICAgICBtdXRhYmxlIHN0YXR1cyBtYW5hZ2VtZW50IHdpdGggYSBzdHJpY3RlciBTdGFnZVJlc3VsdCBjb250cmFjdC4KICAgICAgICAiIiIKCiAgICAgICAgcmVzb2x2ZWQgPSBjbHMucmVzb2x2ZV9zdGFnZSgKICAgICAgICAgICAgc3RhZ2VfcmVzdWx0CiAgICAgICAgKQogICAgICAgIHN0YWdlX3Jlc3VsdC5zdGF0dXMgPSByZXNvbHZlZAogICAgICAgIHJldHVybiByZXNvbHZlZAoKCmNsYXNzIFJlc3VsdE5vcm1hbGl6ZXI6CiAgICAiIiIKICAgIENlbnRyYWwgYXV0aG9yaXR5IGZvciBmaW5kaW5nIG5vcm1hbGl6YXRpb24uCgogICAgUnVsZXMgYXJlIGRldGVybWluaXN0aWM6CiAgICAgICAgLSBvcmRlcmVkIGJ5IHByaW9yaXR5IGFuZCBydWxlX2lkOwogICAgICAgIC0gZmlyc3QgYXBwbGljYWJsZSBub24tS0VFUCBkZWNpc2lvbiB3aW5zOwogICAgICAgIC0gZXZlcnkgcmVtb3ZhbC9yZXBsYWNlbWVudCBpcyBhdWRpdGVkOwogICAgICAgIC0gc3RhZ2Ugc3RhdHVzIGlzIHJlY2FsY3VsYXRlZCBhZnRlciBub3JtYWxpemF0aW9uLgogICAgIiIiCgogICAgZGVmIF9faW5pdF9fKAogICAgICAgIHNlbGYsCiAgICAgICAgcnVsZXM6IEl0ZXJhYmxlW0ZpbmRpbmdOb3JtYWxpemF0aW9uUnVsZV0gPSAoKSwKICAgICkgLT4gTm9uZToKICAgICAgICBzZWxmLl9ydWxlcyA9IHR1cGxlKAogICAgICAgICAgICBzb3J0ZWQoCiAgICAgICAgICAgICAgICBydWxlcywKICAgICAgICAgICAgICAgIGtleT1sYW1iZGEgcnVsZTogKAogICAgICAgICAgICAgICAgICAgIHJ1bGUucHJpb3JpdHksCiAgICAgICAgICAgICAgICAgICAgcnVsZS5ydWxlX2lkLAogICAgICAgICAgICAgICAgKSwKICAgICAgICAgICAgKQogICAgICAgICkKCiAgICAgICAgcnVsZV9pZHMgPSBbCiAgICAgICAgICAgIHJ1bGUucnVsZV9pZAogICAgICAgICAgICBmb3IgcnVsZSBpbiBzZWxmLl9ydWxlcwogICAgICAgIF0KCiAgICAgICAgaWYgbGVuKHJ1bGVfaWRzKSAhPSBsZW4oc2V0KHJ1bGVfaWRzKSk6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICAgICAiUmVzdWx0Tm9ybWFsaXplciBydWxlIGlkZW50aWZpZXJzIG11c3QgYmUgdW5pcXVlLiIKICAgICAgICAgICAgKQoKICAgIEBwcm9wZXJ0eQogICAgZGVmIHJ1bGVzKHNlbGYpIC0+IHR1cGxlW0ZpbmRpbmdOb3JtYWxpemF0aW9uUnVsZSwgLi4uXToKICAgICAgICByZXR1cm4gc2VsZi5fcnVsZXMKCiAgICBkZWYgbm9ybWFsaXplX3N0YWdlKAogICAgICAgIHNlbGYsCiAgICAgICAgKiwKICAgICAgICBzdGFnZV9yZXN1bHQ6IFN0YWdlUmVzdWx0LAogICAgICAgIHZhbGlkYXRpb25fY29udGV4dDogVmFsaWRhdGlvbkNvbnRleHQsCiAgICApIC0+IE5vcm1hbGl6ZWRTdGFnZVNuYXBzaG90OgogICAgICAgIGNvbnRleHQgPSBSZXN1bHROb3JtYWxpemF0aW9uQ29udGV4dC5mcm9tX3N0YWdlKAogICAgICAgICAgICB2YWxpZGF0aW9uX2NvbnRleHQ9dmFsaWRhdGlvbl9jb250ZXh0LAogICAgICAgICAgICBzdGFnZV9yZXN1bHQ9c3RhZ2VfcmVzdWx0LAogICAgICAgICkKCiAgICAgICAgbm9ybWFsaXplZF9maW5kaW5nczogbGlzdFtWYWxpZGF0aW9uRmluZGluZ10gPSBbXQogICAgICAgIGF1ZGl0OiBsaXN0W05vcm1hbGl6YXRpb25BdWRpdFJlY29yZF0gPSBbXQoKICAgICAgICBmb3IgZmluZGluZyBpbiBjb250ZXh0Lm9yaWdpbmFsX2ZpbmRpbmdzOgogICAgICAgICAgICBub3JtYWxpemVkLCBhdWRpdF9yZWNvcmQgPSBzZWxmLl9ub3JtYWxpemVfZmluZGluZygKICAgICAgICAgICAgICAgIGZpbmRpbmc9ZmluZGluZywKICAgICAgICAgICAgICAgIGNvbnRleHQ9Y29udGV4dCwKICAgICAgICAgICAgKQoKICAgICAgICAgICAgaWYgYXVkaXRfcmVjb3JkIGlzIG5vdCBOb25lOgogICAgICAgICAgICAgICAgYXVkaXQuYXBwZW5kKGF1ZGl0X3JlY29yZCkKCiAgICAgICAgICAgIGlmIG5vcm1hbGl6ZWQgaXMgbm90IE5vbmU6CiAgICAgICAgICAgICAgICBub3JtYWxpemVkX2ZpbmRpbmdzLmFwcGVuZChub3JtYWxpemVkKQoKICAgICAgICBjYW5vbmljYWxfc3RhdHVzID0gU3RhdHVzUmVzb2x2ZXIucmVzb2x2ZV9maW5kaW5ncygKICAgICAgICAgICAgbm9ybWFsaXplZF9maW5kaW5ncwogICAgICAgICkKCiAgICAgICAgcmV0dXJuIE5vcm1hbGl6ZWRTdGFnZVNuYXBzaG90KAogICAgICAgICAgICBzdGFnZT1zdGFnZV9yZXN1bHQuc3RhZ2UsCiAgICAgICAgICAgIGZpbmRpbmdzPXR1cGxlKG5vcm1hbGl6ZWRfZmluZGluZ3MpLAogICAgICAgICAgICBjaGVja3NfZXhlY3V0ZWQ9c3RhZ2VfcmVzdWx0LmNoZWNrc19leGVjdXRlZCwKICAgICAgICAgICAgc3RhcnRlZF9hdD1zdGFnZV9yZXN1bHQuc3RhcnRlZF9hdCwKICAgICAgICAgICAgZmluaXNoZWRfYXQ9c3RhZ2VfcmVzdWx0LmZpbmlzaGVkX2F0LAogICAgICAgICAgICBkdXJhdGlvbl9zZWNvbmRzPXN0YWdlX3Jlc3VsdC5kdXJhdGlvbl9zZWNvbmRzLAogICAgICAgICAgICBzdGF0dXM9Y2Fub25pY2FsX3N0YXR1cywKICAgICAgICAgICAgYXVkaXQ9dHVwbGUoYXVkaXQpLAogICAgICAgICkKCiAgICBkZWYgYXBwbHlfdG9fc3RhZ2UoCiAgICAgICAgc2VsZiwKICAgICAgICAqLAogICAgICAgIHN0YWdlX3Jlc3VsdDogU3RhZ2VSZXN1bHQsCiAgICAgICAgdmFsaWRhdGlvbl9jb250ZXh0OiBWYWxpZGF0aW9uQ29udGV4dCwKICAgICkgLT4gTm9ybWFsaXplZFN0YWdlU25hcHNob3Q6CiAgICAgICAgIiIiCiAgICAgICAgTm9ybWFsaXplIGZpbmRpbmdzIGFuZCBzeW5jaHJvbml6ZSB0aGUgbGVnYWN5IFN0YWdlUmVzdWx0IG9iamVjdC4KCiAgICAgICAgVGhpcyBtZXRob2QgaXMgdGhlIFBhcnQgSSBjb21wYXRpYmlsaXR5IGJyaWRnZS4gTGF0ZXIgcGFydHMgd2lsbAogICAgICAgIG1ha2UgTm9ybWFsaXplZFN0YWdlU25hcHNob3QgdGhlIHBpcGVsaW5lJ3MgZGlyZWN0IHJldHVybiB0eXBlLgogICAgICAgICIiIgoKICAgICAgICBzbmFwc2hvdCA9IHNlbGYubm9ybWFsaXplX3N0YWdlKAogICAgICAgICAgICBzdGFnZV9yZXN1bHQ9c3RhZ2VfcmVzdWx0LAogICAgICAgICAgICB2YWxpZGF0aW9uX2NvbnRleHQ9dmFsaWRhdGlvbl9jb250ZXh0LAogICAgICAgICkKCiAgICAgICAgc3RhZ2VfcmVzdWx0LmZpbmRpbmdzWzpdID0gbGlzdCgKICAgICAgICAgICAgc25hcHNob3QuZmluZGluZ3MKICAgICAgICApCiAgICAgICAgc3RhZ2VfcmVzdWx0LnN0YXR1cyA9IHNuYXBzaG90LnN0YXR1cwoKICAgICAgICByZXR1cm4gc25hcHNob3QKCiAgICBkZWYgbm9ybWFsaXplX3N0YWdlcygKICAgICAgICBzZWxmLAogICAgICAgICosCiAgICAgICAgc3RhZ2VfcmVzdWx0czogSXRlcmFibGVbU3RhZ2VSZXN1bHRdLAogICAgICAgIHZhbGlkYXRpb25fY29udGV4dDogVmFsaWRhdGlvbkNvbnRleHQsCiAgICApIC0+IHR1cGxlW05vcm1hbGl6ZWRTdGFnZVNuYXBzaG90LCAuLi5dOgogICAgICAgIHJldHVybiB0dXBsZSgKICAgICAgICAgICAgc2VsZi5hcHBseV90b19zdGFnZSgKICAgICAgICAgICAgICAgIHN0YWdlX3Jlc3VsdD1zdGFnZV9yZXN1bHQsCiAgICAgICAgICAgICAgICB2YWxpZGF0aW9uX2NvbnRleHQ9dmFsaWRhdGlvbl9jb250ZXh0LAogICAgICAgICAgICApCiAgICAgICAgICAgIGZvciBzdGFnZV9yZXN1bHQgaW4gc3RhZ2VfcmVzdWx0cwogICAgICAgICkKCiAgICBkZWYgX25vcm1hbGl6ZV9maW5kaW5nKAogICAgICAgIHNlbGYsCiAgICAgICAgKiwKICAgICAgICBmaW5kaW5nOiBWYWxpZGF0aW9uRmluZGluZywKICAgICAgICBjb250ZXh0OiBSZXN1bHROb3JtYWxpemF0aW9uQ29udGV4dCwKICAgICkgLT4gdHVwbGVbCiAgICAgICAgVmFsaWRhdGlvbkZpbmRpbmcgfCBOb25lLAogICAgICAgIE5vcm1hbGl6YXRpb25BdWRpdFJlY29yZCB8IE5vbmUsCiAgICBdOgogICAgICAgIGZvciBydWxlIGluIHNlbGYuX3J1bGVzOgogICAgICAgICAgICBpZiBub3QgcnVsZS5hcHBsaWVzX3RvKAogICAgICAgICAgICAgICAgZmluZGluZz1maW5kaW5nLAogICAgICAgICAgICAgICAgY29udGV4dD1jb250ZXh0LAogICAgICAgICAgICApOgogICAgICAgICAgICAgICAgY29udGludWUKCiAgICAgICAgICAgIGRlY2lzaW9uID0gcnVsZS5kZWNpc2lvbl9mYWN0b3J5KAogICAgICAgICAgICAgICAgZmluZGluZywKICAgICAgICAgICAgICAgIGNvbnRleHQsCiAgICAgICAgICAgICkKCiAgICAgICAgICAgIGlmIGRlY2lzaW9uLmRpc3Bvc2l0aW9uIGlzIEZpbmRpbmdEaXNwb3NpdGlvbi5LRUVQOgogICAgICAgICAgICAgICAgY29udGludWUKCiAgICAgICAgICAgIGF1ZGl0ID0gTm9ybWFsaXphdGlvbkF1ZGl0UmVjb3JkKAogICAgICAgICAgICAgICAgcnVsZV9pZD1ydWxlLnJ1bGVfaWQsCiAgICAgICAgICAgICAgICBzdGFnZT1jb250ZXh0LnN0YWdlLAogICAgICAgICAgICAgICAgZmluZGluZ19jb2RlPWZpbmRpbmcuY29kZSwKICAgICAgICAgICAgICAgIGRpc3Bvc2l0aW9uPWRlY2lzaW9uLmRpc3Bvc2l0aW9uLAogICAgICAgICAgICAgICAgcmVhc29uPWRlY2lzaW9uLnJlYXNvbiwKICAgICAgICAgICAgKQoKICAgICAgICAgICAgaWYgZGVjaXNpb24uZGlzcG9zaXRpb24gaXMgRmluZGluZ0Rpc3Bvc2l0aW9uLlJFTU9WRToKICAgICAgICAgICAgICAgIHJldHVybiBOb25lLCBhdWRpdAoKICAgICAgICAgICAgaWYgZGVjaXNpb24uZGlzcG9zaXRpb24gaXMgRmluZGluZ0Rpc3Bvc2l0aW9uLlJFUExBQ0U6CiAgICAgICAgICAgICAgICByZXR1cm4gZGVjaXNpb24ucmVwbGFjZW1lbnQsIGF1ZGl0CgogICAgICAgICAgICByYWlzZSBWYWxpZGF0aW9uRXhlY3V0aW9uRXJyb3IoCiAgICAgICAgICAgICAgICAiVW5zdXBwb3J0ZWQgZmluZGluZyBub3JtYWxpemF0aW9uIGRpc3Bvc2l0aW9uOiAiCiAgICAgICAgICAgICAgICBmIntkZWNpc2lvbi5kaXNwb3NpdGlvbiFyfS4iCiAgICAgICAgICAgICkKCiAgICAgICAgcmV0dXJuIGZpbmRpbmcsIE5vbmUKCgpjbGFzcyBFeGl0Q29kZVJlc29sdmVyOgogICAgIiIiCiAgICBTaW5nbGUgYXV0aG9yaXR5IGZvciBwcm9jZXNzIGV4aXQtY29kZSByZXNvbHV0aW9uLgogICAgIiIiCgogICAgQHN0YXRpY21ldGhvZAogICAgZGVmIHJlc29sdmUoCiAgICAgICAgKiwKICAgICAgICBzdGF0dXM6IFZhbGlkYXRpb25TdGF0dXMsCiAgICAgICAgc3RyaWN0OiBib29sLAogICAgICAgIGNyaXRpY2FsX2Vycm9yczogaW50ID0gMCwKICAgICkgLT4gRXhpdENvZGU6CiAgICAgICAgaWYgY3JpdGljYWxfZXJyb3JzID4gMDoKICAgICAgICAgICAgcmV0dXJuIEV4aXRDb2RlLlZBTElEQVRJT05fRkFJTFVSRQoKICAgICAgICBpZiBzdGF0dXMgaXMgVmFsaWRhdGlvblN0YXR1cy5GQUlMOgogICAgICAgICAgICByZXR1cm4gRXhpdENvZGUuVkFMSURBVElPTl9GQUlMVVJFCgogICAgICAgIGlmICgKICAgICAgICAgICAgc3RhdHVzIGlzIFZhbGlkYXRpb25TdGF0dXMuV0FSTklORwogICAgICAgICAgICBhbmQgc3RyaWN0CiAgICAgICAgKToKICAgICAgICAgICAgcmV0dXJuIEV4aXRDb2RlLlZBTElEQVRJT05fV0FSTklORwoKICAgICAgICByZXR1cm4gRXhpdENvZGUuU1VDQ0VTUwoKICAgIEBjbGFzc21ldGhvZAogICAgZGVmIHJlc29sdmVfcmVwb3J0KAogICAgICAgIGNscywKICAgICAgICAqLAogICAgICAgIHJlcG9ydDogVmFsaWRhdGlvblJlcG9ydCwKICAgICAgICBzdHJpY3Q6IGJvb2wsCiAgICApIC0+IEV4aXRDb2RlOgogICAgICAgIGNhbm9uaWNhbF9zdGF0dXMgPSBTdGF0dXNSZXNvbHZlci5yZXNvbHZlX3JlcG9ydCgKICAgICAgICAgICAgcmVwb3J0LnN0YWdlcwogICAgICAgICkKCiAgICAgICAgcmV0dXJuIGNscy5yZXNvbHZlKAogICAgICAgICAgICBzdGF0dXM9Y2Fub25pY2FsX3N0YXR1cywKICAgICAgICAgICAgc3RyaWN0PXN0cmljdCwKICAgICAgICAgICAgY3JpdGljYWxfZXJyb3JzPXJlcG9ydC5jcml0aWNhbF9lcnJvcnMsCiAgICAgICAgKQoKCmRlZiBidWlsZF9yZXN1bHRfbm9ybWFsaXplcigpIC0+IFJlc3VsdE5vcm1hbGl6ZXI6CiAgICAiIiIKICAgIEJ1aWxkIHRoZSBjYW5vbmljYWwgbm9ybWFsaXplci4KCiAgICBQYXJ0IEkgaW50ZW50aW9uYWxseSByZWdpc3RlcnMgbm8gYmVoYXZpb3JhbCBydWxlcy4gVGVybWluYWwtZ3JhcGgKICAgIGFuZCBsZWdhY3kgY29tcGF0aWJpbGl0eSBydWxlcyB3aWxsIGJlIG1pZ3JhdGVkIGluIFBhcnRzIElWIGFuZCBWLgogICAgIiIiCgogICAgcmV0dXJuIFJlc3VsdE5vcm1hbGl6ZXIoCiAgICAgICAgcnVsZXM9KCkKICAgICkKCgojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiMgRU5EIE9GIENUUkwtMDE4IOKAlCBQQVJUIEkKIyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQo="
).decode("utf-8")

SUPPORT_CODE = base64.b64decode(
    "CiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBDVFJMLTAxOCDigJQgVkFMSURBVE9SIFJFU1VMVCBDT05TSVNURU5DWSBSRUZBQ1RPUgojIElOVEVHUkFURUQgQ09OU0lTVEVOQ1kgU1VQUE9SVAojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CgpfU1RBR0VfTUVUQURBVEFfS0VZUzogRmluYWxbTWFwcGluZ1tTdGFnZU5hbWUsIHN0cl1dID0gewogICAgU3RhZ2VOYW1lLlJFUE9TSVRPUlk6ICJyZXBvc2l0b3J5X3ZhbGlkYXRlZCIsCiAgICBTdGFnZU5hbWUuQ09OVFJBQ1RTOiAiY29udHJhY3RzX3ZhbGlkYXRlZCIsCiAgICBTdGFnZU5hbWUuTUFOSUZFU1Q6ICJtYW5pZmVzdF92YWxpZGF0ZWQiLAogICAgU3RhZ2VOYW1lLkRFUEVOREVOQ0lFUzogImRlcGVuZGVuY2llc192YWxpZGF0ZWQiLAogICAgU3RhZ2VOYW1lLlBST0pFQ1RfQ09OVFJPTDogInByb2plY3RfY29udHJvbF92YWxpZGF0ZWQiLAogICAgU3RhZ2VOYW1lLkJBU0VMSU5FOiAiYmFzZWxpbmVfdmFsaWRhdGVkIiwKICAgIFN0YWdlTmFtZS5DRVJUSUZJQ0FUSU9OOiAiY2VydGlmaWNhdGlvbl92YWxpZGF0ZWQiLAp9CgoKZGVmIHN5bmNocm9uaXplX3N0YWdlX21ldGFkYXRhKAogICAgKiwKICAgIGNvbnRleHQ6IFZhbGlkYXRpb25Db250ZXh0LAogICAgc3RhZ2VfcmVzdWx0OiBTdGFnZVJlc3VsdCwKKSAtPiBOb25lOgogICAgIiIiCiAgICBTeW5jaHJvbml6ZSBzaGFyZWQgc3RhZ2UgbWV0YWRhdGEgZnJvbSB0aGUgY2Fub25pY2FsIHN0YWdlIHJlc3VsdC4KCiAgICBDZXJ0aWZpY2F0aW9uIG11c3QgY29uc3VtZSB0aGUgc2FtZSBub3JtYWxpemVkIHRydXRoIHVzZWQgYnkgdGhlCiAgICByZXBvcnQgYW5kIHRoZSBwcm9jZXNzIGV4aXQtY29kZSByZXNvbHZlci4KICAgICIiIgoKICAgIG1ldGFkYXRhX2tleSA9IF9TVEFHRV9NRVRBREFUQV9LRVlTLmdldCgKICAgICAgICBzdGFnZV9yZXN1bHQuc3RhZ2UKICAgICkKCiAgICBpZiBtZXRhZGF0YV9rZXkgaXMgbm90IE5vbmU6CiAgICAgICAgY29udGV4dC5tZXRhZGF0YVttZXRhZGF0YV9rZXldID0gKAogICAgICAgICAgICBzdGFnZV9yZXN1bHQucGFzc2VkCiAgICAgICAgKQoKCmRlZiBub3JtYWxpemVfcGlwZWxpbmVfc3RhZ2VfcmVzdWx0KAogICAgKiwKICAgIGNvbnRleHQ6IFZhbGlkYXRpb25Db250ZXh0LAogICAgc3RhZ2VfcmVzdWx0OiBTdGFnZVJlc3VsdCwKKSAtPiBTdGFnZVJlc3VsdDoKICAgICIiIgogICAgTm9ybWFsaXplIG9uZSBjb21wbGV0ZWQgc3RhZ2UgYW5kIHN5bmNocm9uaXplIGFsbCBkZXJpdmVkIHN0YXRlLgogICAgIiIiCgogICAgU3RhdHVzUmVzb2x2ZXIuc3luY2hyb25pemVfc3RhZ2Vfc3RhdHVzKAogICAgICAgIHN0YWdlX3Jlc3VsdAogICAgKQogICAgc3luY2hyb25pemVfc3RhZ2VfbWV0YWRhdGEoCiAgICAgICAgY29udGV4dD1jb250ZXh0LAogICAgICAgIHN0YWdlX3Jlc3VsdD1zdGFnZV9yZXN1bHQsCiAgICApCiAgICByZXR1cm4gc3RhZ2VfcmVzdWx0CgoKZGVmIGFzc2VydF9zdGFnZV9yZXN1bHRfY29uc2lzdGVuY3koCiAgICBzdGFnZV9yZXN1bHQ6IFN0YWdlUmVzdWx0LAopIC0+IE5vbmU6CiAgICAiIiIKICAgIFJhaXNlIHdoZW4gYSBTdGFnZVJlc3VsdCBjb250YWlucyBzdGFsZSBzdGF0dXMgaW5mb3JtYXRpb24uCiAgICAiIiIKCiAgICBleHBlY3RlZCA9IFN0YXR1c1Jlc29sdmVyLnJlc29sdmVfc3RhZ2UoCiAgICAgICAgc3RhZ2VfcmVzdWx0CiAgICApCgogICAgaWYgc3RhZ2VfcmVzdWx0LnN0YXR1cyBpcyBub3QgZXhwZWN0ZWQ6CiAgICAgICAgcmFpc2UgVmFsaWRhdGlvbkV4ZWN1dGlvbkVycm9yKAogICAgICAgICAgICAiU3RhZ2VSZXN1bHQgc3RhdHVzIGlzIGluY29uc2lzdGVudCB3aXRoIGl0cyBmaW5kaW5nczogIgogICAgICAgICAgICBmInN0YWdlPXtzdGFnZV9yZXN1bHQuc3RhZ2UudmFsdWUhcn0sICIKICAgICAgICAgICAgZiJzdG9yZWQ9e3N0YWdlX3Jlc3VsdC5zdGF0dXMudmFsdWUhcn0sICIKICAgICAgICAgICAgZiJleHBlY3RlZD17ZXhwZWN0ZWQudmFsdWUhcn0uIgogICAgICAgICkKCiAgICBibG9ja2luZyA9ICgKICAgICAgICBzdGFnZV9yZXN1bHQuZXJyb3JzCiAgICAgICAgKyBzdGFnZV9yZXN1bHQuY3JpdGljYWxfZXJyb3JzCiAgICApCgogICAgaWYgKAogICAgICAgIHN0YWdlX3Jlc3VsdC5zdGF0dXMgaXMgVmFsaWRhdGlvblN0YXR1cy5GQUlMCiAgICAgICAgYW5kIGJsb2NraW5nID09IDAKICAgICk6CiAgICAgICAgcmFpc2UgVmFsaWRhdGlvbkV4ZWN1dGlvbkVycm9yKAogICAgICAgICAgICAiQSBzdGFnZSBjYW5ub3QgYmUgRkFJTCB3aXRob3V0IGFuIEVSUk9SIG9yIENSSVRJQ0FMIGZpbmRpbmc6ICIKICAgICAgICAgICAgZiJ7c3RhZ2VfcmVzdWx0LnN0YWdlLnZhbHVlIXJ9LiIKICAgICAgICApCgogICAgaWYgKAogICAgICAgIHN0YWdlX3Jlc3VsdC5zdGF0dXMgaXMgbm90IFZhbGlkYXRpb25TdGF0dXMuRkFJTAogICAgICAgIGFuZCBibG9ja2luZyA+IDAKICAgICk6CiAgICAgICAgcmFpc2UgVmFsaWRhdGlvbkV4ZWN1dGlvbkVycm9yKAogICAgICAgICAgICAiQSBzdGFnZSBjb250YWluaW5nIGJsb2NraW5nIGZpbmRpbmdzIG11c3QgYmUgRkFJTDogIgogICAgICAgICAgICBmIntzdGFnZV9yZXN1bHQuc3RhZ2UudmFsdWUhcn0uIgogICAgICAgICkKCgpkZWYgYXNzZXJ0X3JlcG9ydF9jb25zaXN0ZW5jeSgKICAgIHJlcG9ydDogVmFsaWRhdGlvblJlcG9ydCwKKSAtPiBOb25lOgogICAgIiIiCiAgICBWYWxpZGF0ZSByZXBvcnQsIHN0YWdlIGFuZCBhZ2dyZWdhdGUgc3RhdHVzIGludmFyaWFudHMuCiAgICAiIiIKCiAgICBmb3Igc3RhZ2VfcmVzdWx0IGluIHJlcG9ydC5zdGFnZXM6CiAgICAgICAgYXNzZXJ0X3N0YWdlX3Jlc3VsdF9jb25zaXN0ZW5jeSgKICAgICAgICAgICAgc3RhZ2VfcmVzdWx0CiAgICAgICAgKQoKICAgIGNhbm9uaWNhbCA9IFN0YXR1c1Jlc29sdmVyLnJlc29sdmVfcmVwb3J0KAogICAgICAgIHJlcG9ydC5zdGFnZXMKICAgICkKCiAgICBpZiByZXBvcnQuc3RhdHVzIGlzIG5vdCBjYW5vbmljYWw6CiAgICAgICAgcmFpc2UgVmFsaWRhdGlvbkV4ZWN1dGlvbkVycm9yKAogICAgICAgICAgICAiVmFsaWRhdGlvblJlcG9ydCBzdGF0dXMgaXMgaW5jb25zaXN0ZW50IHdpdGggbm9ybWFsaXplZCAiCiAgICAgICAgICAgIGYic3RhZ2UgcmVzdWx0czogc3RvcmVkPXtyZXBvcnQuc3RhdHVzLnZhbHVlIXJ9LCAiCiAgICAgICAgICAgIGYiZXhwZWN0ZWQ9e2Nhbm9uaWNhbC52YWx1ZSFyfS4iCiAgICAgICAgKQoKCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBFTkQgQ1RSTC0wMTggSU5URUdSQVRFRCBDT05TSVNURU5DWSBTVVBQT1JUCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0K"
).decode("utf-8")


OLD_REPORT_STATUS = """    @property
    def status(self) -> ValidationStatus:
        \"\"\"Calculate the final validation status.\"\"\"

        if any(
            stage.status is ValidationStatus.FAIL
            for stage in self.stages
        ):
            return ValidationStatus.FAIL

        if any(
            stage.status is ValidationStatus.WARNING
            for stage in self.stages
        ):
            return ValidationStatus.WARNING

        if self.stages and all(
            stage.status is ValidationStatus.SKIPPED
            for stage in self.stages
        ):
            return ValidationStatus.SKIPPED

        return ValidationStatus.PASS
"""

NEW_REPORT_STATUS = """    @property
    def status(self) -> ValidationStatus:
        \"\"\"Calculate status from normalized stage findings.\"\"\"

        return StatusResolver.resolve_report(
            self.stages
        )
"""

OLD_ADD_STAGE = """    def add_stage(self, stage_result: StageResult) -> None:
        \"\"\"Add a completed stage result.\"\"\"

        self.stages.append(stage_result)
"""

NEW_ADD_STAGE = """    def add_stage(self, stage_result: StageResult) -> None:
        \"\"\"Add a completed, canonically normalized stage result.\"\"\"

        StatusResolver.synchronize_stage_status(
            stage_result
        )
        self.stages.append(stage_result)
"""

OLD_RUN_STAGE_TAIL = """        finished_at = datetime.now(timezone.utc)

        result.started_at = started_at
        result.finished_at = finished_at
        result.duration_seconds = time.perf_counter() - started_timer

        return result
"""

NEW_RUN_STAGE_TAIL = """        result = normalize_pipeline_stage_result(
            context=self._context,
            stage_result=result,
        )

        finished_at = datetime.now(timezone.utc)

        result.started_at = started_at
        result.finished_at = finished_at
        result.duration_seconds = time.perf_counter() - started_timer

        assert_stage_result_consistency(
            result
        )

        return result
"""

OLD_EXECUTE_VALIDATION_RETURN = """    return pipeline.run()
"""

NEW_EXECUTE_VALIDATION_RETURN = """    report = pipeline.run()

    assert_report_consistency(
        report
    )

    return report
"""

OLD_EXIT_CODE = """def resolve_exit_code(
    report: ValidationReport,
    *,
    strict: bool,
) -> ExitCode:
    \"\"\"Resolve the process exit code from the validation report.\"\"\"

    if report.status is ValidationStatus.FAIL:
        return ExitCode.VALIDATION_FAILURE

    if (
        report.status is ValidationStatus.WARNING
        and strict
    ):
        return ExitCode.VALIDATION_WARNING

    return ExitCode.SUCCESS
"""

NEW_EXIT_CODE = """def resolve_exit_code(
    report: ValidationReport,
    *,
    strict: bool,
) -> ExitCode:
    \"\"\"Resolve exit code from the canonical normalized report.\"\"\"

    assert_report_consistency(
        report
    )

    return ExitCodeResolver.resolve_report(
        report=report,
        strict=strict,
    )
"""


def syntax_check(text: str, filename: str) -> None:
    ast.parse(
        text,
        filename=filename,
    )


def replace_exactly_once(
    text: str,
    old: str,
    new: str,
    label: str,
) -> str:
    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} block; found {count}."
        )

    return text.replace(
        old,
        new,
        1,
    )


def install_part_i_if_missing(text: str) -> str:
    if "class ResultNormalizer:" in text:
        return text

    count = text.count(STAGE_CONTRACT_MARKER)

    if count != 1:
        raise RuntimeError(
            "Unable to install Part I: expected exactly one "
            f"Validation Stage Contract marker; found {count}."
        )

    return text.replace(
        STAGE_CONTRACT_MARKER,
        PART_I_CODE.rstrip()
        + "\n\n"
        + STAGE_CONTRACT_MARKER,
        1,
    )


def insert_support_block(text: str) -> str:
    if INTEGRATED_MARKER in text:
        raise RuntimeError(
            "The integrated CTRL-018 refactor is already installed."
        )

    count = text.count(STAGE_CONTRACT_MARKER)

    if count != 1:
        raise RuntimeError(
            "Expected exactly one Validation Stage Contract marker "
            f"for support insertion; found {count}."
        )

    return text.replace(
        STAGE_CONTRACT_MARKER,
        SUPPORT_CODE.rstrip()
        + "\n\n"
        + STAGE_CONTRACT_MARKER,
        1,
    )


def run_regression_test(target: Path) -> None:
    test_code = r"""
import importlib.util
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "ctrl018_validator_test",
    path,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

stage = module.StageResult(
    stage=module.StageName.DEPENDENCIES
)
stage.add_finding(
    module.info_finding(
        code="CTRL018-TEST-INFO",
        message="non-blocking test finding",
        stage=module.StageName.DEPENDENCIES,
    )
)
stage.status = module.ValidationStatus.FAIL

module.StatusResolver.synchronize_stage_status(stage)
module.assert_stage_result_consistency(stage)

if stage.status is not module.ValidationStatus.PASS:
    raise SystemExit("Stage normalization did not produce PASS.")

report = module.ValidationReport()
report.add_stage(stage)
report.finish()
module.assert_report_consistency(report)

if report.status is not module.ValidationStatus.PASS:
    raise SystemExit("Report normalization did not produce PASS.")

exit_code = module.ExitCodeResolver.resolve_report(
    report=report,
    strict=False,
)

if exit_code is not module.ExitCode.SUCCESS:
    raise SystemExit("Exit code normalization did not produce SUCCESS.")

print("CTRL-018 consistency regression: PASS")
"""

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            test_code,
            str(target),
        ],
        cwd=str(target.parent),
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        details = (
            completed.stdout
            + completed.stderr
        ).strip()
        raise RuntimeError(
            "CTRL-018 regression test failed: "
            + details
        )


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    target = script_directory / TARGET_NAME

    if not target.is_file():
        print(
            f"ERROR: File not found: {target}",
            file=sys.stderr,
        )
        return 2

    original = target.read_text(
        encoding="utf-8"
    )

    if INTEGRATED_MARKER in original:
        print("NO CHANGES REQUIRED")
        print(
            "The integrated CTRL-018 consistency refactor "
            "is already installed."
        )
        return 0

    required_base_symbols = (
        "class StageResult:",
        "class ValidationReport:",
        "class ValidationPipeline:",
        "def execute_validation(",
        "def resolve_exit_code(",
    )

    missing = [
        symbol
        for symbol in required_base_symbols
        if symbol not in original
    ]

    if missing:
        print(
            "ERROR: Required validator symbols are missing:",
            file=sys.stderr,
        )
        for symbol in missing:
            print(
                f"- {symbol}",
                file=sys.stderr,
            )
        return 3

    updated = install_part_i_if_missing(
        original
    )
    updated = insert_support_block(
        updated
    )
    updated = replace_exactly_once(
        updated,
        OLD_REPORT_STATUS,
        NEW_REPORT_STATUS,
        "ValidationReport.status",
    )
    updated = replace_exactly_once(
        updated,
        OLD_ADD_STAGE,
        NEW_ADD_STAGE,
        "ValidationReport.add_stage",
    )
    updated = replace_exactly_once(
        updated,
        OLD_RUN_STAGE_TAIL,
        NEW_RUN_STAGE_TAIL,
        "ValidationPipeline._run_stage tail",
    )
    updated = replace_exactly_once(
        updated,
        OLD_EXECUTE_VALIDATION_RETURN,
        NEW_EXECUTE_VALIDATION_RETURN,
        "execute_validation return",
    )
    updated = replace_exactly_once(
        updated,
        OLD_EXIT_CODE,
        NEW_EXIT_CODE,
        "resolve_exit_code",
    )

    try:
        syntax_check(
            updated,
            str(target),
        )
    except Exception as error:
        print(
            "PATCH NOT APPLIED",
            file=sys.stderr,
        )
        print(
            f"Pre-write verification failed: {error}",
            file=sys.stderr,
        )
        return 4

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )
    backup = target.with_name(
        f"{target.name}."
        f"bak_ctrl018_integrated_{timestamp}"
    )

    try:
        shutil.copy2(
            target,
            backup,
        )
        target.write_text(
            updated,
            encoding="utf-8",
        )

        verification = target.read_text(
            encoding="utf-8"
        )
        syntax_check(
            verification,
            str(target),
        )

        verification_markers = (
            "class ResultNormalizer:",
            "class StatusResolver:",
            "class ExitCodeResolver:",
            "def normalize_pipeline_stage_result(",
            "def assert_stage_result_consistency(",
            "def assert_report_consistency(",
            "return StatusResolver.resolve_report(",
            "return ExitCodeResolver.resolve_report(",
        )

        absent = [
            marker
            for marker in verification_markers
            if marker not in verification
        ]

        if absent:
            raise RuntimeError(
                "Post-write verification markers missing: "
                + ", ".join(absent)
            )

        run_regression_test(
            target
        )

    except Exception as error:
        if backup.is_file():
            shutil.copy2(
                backup,
                target,
            )

        print(
            "PATCH ROLLED BACK",
            file=sys.stderr,
        )
        print(
            f"Reason: {error}",
            file=sys.stderr,
        )
        return 5

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("CTRL-018 integrated refactor installed:")
    print("- Canonical StageResult status resolution")
    print("- Canonical ValidationReport aggregation")
    print("- Pipeline post-stage normalization")
    print("- Shared metadata synchronization")
    print("- Report consistency invariants")
    print("- Single exit-code resolver")
    print("- Isolated regression test: PASS")
    print()
    print("No YAML or Markdown files were modified.")
    print()
    print("Next safe command:")
    print(
        "python -B validate_project_control.py --verbose"
    )
    print()
    print(
        "Do not run finalize_ctrl016.py until the validator "
        "result has been reviewed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )