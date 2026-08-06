#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TARGET_NAME = "sync_project_control.py"
PART_CODE_B64 = "CiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBUSFJFRS1GSUxFIFRSQU5TQUNUSU9OIOKAlCBQQVJUIFZJSQojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CgpkZWYgcmVwbGFjZV9tYW5pZmVzdF9lbnRyeV9zdGF0dXMoCiAgICB0ZXh0OiBzdHIsCiAgICAqLAogICAgZmlsZV9pZDogc3RyLAogICAgc3RhdHVzOiBzdHIKKSAtPiBzdHI6CiAgICAiIiIKICAgIFJlcGxhY2UgdGhlIHN0YXR1cyBmaWVsZCBpbnNpZGUgb25lIEZJTEUtWFhYWFggcmVjb3JkIHdpdGhvdXQKICAgIHJlc2VyaWFsaXppbmcgdGhlIGNvbXBsZXRlIFlBTUwgZG9jdW1lbnQuCiAgICAiIiIKCiAgICBsaW5lcyA9IHRleHQuc3BsaXRsaW5lcyhrZWVwZW5kcz1UcnVlKQoKICAgIGVudHJ5X3BhdHRlcm4gPSByZS5jb21waWxlKAogICAgICAgIHJmIl4gIHtyZS5lc2NhcGUoZmlsZV9pZCl9OlxzKiQiCiAgICApCgogICAgbWF0Y2hlcyA9IFsKICAgICAgICBpbmRleAogICAgICAgIGZvciBpbmRleCwgbGluZSBpbiBlbnVtZXJhdGUobGluZXMpCiAgICAgICAgaWYgZW50cnlfcGF0dGVybi5tYXRjaChsaW5lLnJzdHJpcCgiXHJcbiIpKQogICAgXQoKICAgIGlmIGxlbihtYXRjaGVzKSAhPSAxOgogICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgIGYiRXhwZWN0ZWQgZXhhY3RseSBvbmUgbWFuaWZlc3QgZW50cnkge2ZpbGVfaWQhcn07ICIKICAgICAgICAgICAgZiJmb3VuZCB7bGVuKG1hdGNoZXMpfS4iCiAgICAgICAgKQoKICAgIHN0YXJ0ID0gbWF0Y2hlc1swXQogICAgZW5kID0gbGVuKGxpbmVzKQoKICAgIGZvciBpbmRleCBpbiByYW5nZShzdGFydCArIDEsIGxlbihsaW5lcykpOgoKICAgICAgICByYXcgPSBsaW5lc1tpbmRleF0ucnN0cmlwKCJcclxuIikKCiAgICAgICAgaWYgcmUubWF0Y2gociJeICBGSUxFLVxkKzpccyokIiwgcmF3KToKICAgICAgICAgICAgZW5kID0gaW5kZXgKICAgICAgICAgICAgYnJlYWsKCiAgICAgICAgaWYgKAogICAgICAgICAgICByYXcKICAgICAgICAgICAgYW5kIG5vdCByYXcuc3RhcnRzd2l0aCgiICIpCiAgICAgICAgICAgIGFuZCBub3QgcmF3LnN0YXJ0c3dpdGgoIiMiKQogICAgICAgICk6CiAgICAgICAgICAgIGVuZCA9IGluZGV4CiAgICAgICAgICAgIGJyZWFrCgogICAgc3RhdHVzX3BhdHRlcm4gPSByZS5jb21waWxlKAogICAgICAgIHIiXiAgICBzdGF0dXM6XHMqKC4qPylccyokIgogICAgKQoKICAgIHN0YXR1c19tYXRjaGVzID0gWwogICAgICAgIGluZGV4CiAgICAgICAgZm9yIGluZGV4IGluIHJhbmdlKHN0YXJ0ICsgMSwgZW5kKQogICAgICAgIGlmIHN0YXR1c19wYXR0ZXJuLm1hdGNoKAogICAgICAgICAgICBsaW5lc1tpbmRleF0ucnN0cmlwKCJcclxuIikKICAgICAgICApCiAgICBdCgogICAgaWYgbGVuKHN0YXR1c19tYXRjaGVzKSAhPSAxOgogICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgIGYiRXhwZWN0ZWQgZXhhY3RseSBvbmUgc3RhdHVzIGZpZWxkIGluIHtmaWxlX2lkIXJ9OyAiCiAgICAgICAgICAgIGYiZm91bmQge2xlbihzdGF0dXNfbWF0Y2hlcyl9LiIKICAgICAgICApCgogICAgdGFyZ2V0ID0gc3RhdHVzX21hdGNoZXNbMF0KICAgIG5ld2xpbmUgPSAoCiAgICAgICAgIlxyXG4iCiAgICAgICAgaWYgbGluZXNbdGFyZ2V0XS5lbmRzd2l0aCgiXHJcbiIpCiAgICAgICAgZWxzZSAiXG4iCiAgICApCgogICAgbGluZXNbdGFyZ2V0XSA9ICgKICAgICAgICAiICAgIHN0YXR1czogIgogICAgICAgIGYie2Zvcm1hdF95YW1sX3NjYWxhcihzdGF0dXMpfSIKICAgICAgICBmIntuZXdsaW5lfSIKICAgICkKCiAgICByZXR1cm4gIiIuam9pbihsaW5lcykKCgpkZWYgaW5zZXJ0X21hbmlmZXN0X2VudHJ5KAogICAgdGV4dDogc3RyLAogICAgKiwKICAgIGZpbGVfaWQ6IHN0ciwKICAgIHJlY29yZDogRGljdFtzdHIsIEFueV0KKSAtPiBzdHI6CiAgICAiIiIKICAgIEluc2VydCBvbmUgRklMRS1YWFhYWCByZWNvcmQgYXQgdGhlIGVuZCBvZiB0aGUgdG9wLWxldmVsIGZpbGVzIG1hcHBpbmcuCiAgICAiIiIKCiAgICBsaW5lcyA9IHRleHQuc3BsaXRsaW5lcyhrZWVwZW5kcz1UcnVlKQoKICAgIGZpbGVzX21hdGNoZXMgPSBbCiAgICAgICAgaW5kZXgKICAgICAgICBmb3IgaW5kZXgsIGxpbmUgaW4gZW51bWVyYXRlKGxpbmVzKQogICAgICAgIGlmIGxpbmUucnN0cmlwKCJcclxuIikgPT0gImZpbGVzOiIKICAgIF0KCiAgICBpZiBsZW4oZmlsZXNfbWF0Y2hlcykgIT0gMToKICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAiRXhwZWN0ZWQgZXhhY3RseSBvbmUgdG9wLWxldmVsICdmaWxlczonIG1hcHBpbmcuIgogICAgICAgICkKCiAgICBmaWxlc19saW5lID0gZmlsZXNfbWF0Y2hlc1swXQogICAgc2VjdGlvbl9lbmQgPSBsZW4obGluZXMpCgogICAgZm9yIGluZGV4IGluIHJhbmdlKGZpbGVzX2xpbmUgKyAxLCBsZW4obGluZXMpKToKCiAgICAgICAgcmF3ID0gbGluZXNbaW5kZXhdLnJzdHJpcCgiXHJcbiIpCgogICAgICAgIGlmIG5vdCByYXcuc3RyaXAoKSBvciByYXcubHN0cmlwKCkuc3RhcnRzd2l0aCgiIyIpOgogICAgICAgICAgICBjb250aW51ZQoKICAgICAgICBpZiAoCiAgICAgICAgICAgIGxpbmVfaW5kZW50YXRpb24ocmF3KSA9PSAwCiAgICAgICAgICAgIGFuZCByZS5tYXRjaChyIl5bQS1aYS16MC05X10rOlxzKiIsIHJhdykKICAgICAgICApOgogICAgICAgICAgICBzZWN0aW9uX2VuZCA9IGluZGV4CiAgICAgICAgICAgIGJyZWFrCgogICAgbmV3bGluZSA9ICJcbiIKCiAgICBpZiBsaW5lcyBhbmQgYW55KAogICAgICAgIGxpbmUuZW5kc3dpdGgoIlxyXG4iKQogICAgICAgIGZvciBsaW5lIGluIGxpbmVzWzogbWluKGxlbihsaW5lcyksIDIwKV0KICAgICk6CiAgICAgICAgbmV3bGluZSA9ICJcclxuIgoKICAgIG9yZGVyZWRfZmllbGRzID0gKAogICAgICAgICJmaWxlbmFtZSIsCiAgICAgICAgInJlbGF0aXZlX3BhdGgiLAogICAgICAgICJleHRlbnNpb24iLAogICAgICAgICJ0eXBlIiwKICAgICAgICAic3Vic3lzdGVtIiwKICAgICAgICAib3duZXIiLAogICAgICAgICJsaWZlY3ljbGUiLAogICAgICAgICJzdGF0dXMiLAogICAgICAgICJwaGFzZSIsCiAgICAgICAgInZlcnNpb24iLAogICAgICAgICJkZWxpdmVyYWJsZV9pZCIKICAgICkKCiAgICBibG9jayA9IFsKICAgICAgICBuZXdsaW5lLAogICAgICAgIGYiICB7ZmlsZV9pZH06e25ld2xpbmV9IgogICAgXQoKICAgIGZvciBmaWVsZF9uYW1lIGluIG9yZGVyZWRfZmllbGRzOgoKICAgICAgICBpZiBmaWVsZF9uYW1lIG5vdCBpbiByZWNvcmQ6CiAgICAgICAgICAgIGNvbnRpbnVlCgogICAgICAgIGJsb2NrLmFwcGVuZCgKICAgICAgICAgICAgIiAgICAiCiAgICAgICAgICAgIGYie2ZpZWxkX25hbWV9OiAiCiAgICAgICAgICAgIGYie2Zvcm1hdF95YW1sX3NjYWxhcihyZWNvcmRbZmllbGRfbmFtZV0pfSIKICAgICAgICAgICAgZiJ7bmV3bGluZX0iCiAgICAgICAgKQoKICAgIGluc2VydF9hdCA9IHNlY3Rpb25fZW5kCgogICAgd2hpbGUgKAogICAgICAgIGluc2VydF9hdCA+IGZpbGVzX2xpbmUgKyAxCiAgICAgICAgYW5kIG5vdCBsaW5lc1tpbnNlcnRfYXQgLSAxXS5zdHJpcCgpCiAgICApOgogICAgICAgIGluc2VydF9hdCAtPSAxCgogICAgbGluZXNbaW5zZXJ0X2F0Omluc2VydF9hdF0gPSBibG9jawoKICAgIHJldHVybiAiIi5qb2luKGxpbmVzKQoKCmRlZiB1cGRhdGVfbWFuaWZlc3Rfc3VtbWFyeV90b3RhbCgKICAgIHRleHQ6IHN0ciwKICAgIHRvdGFsX2VudHJpZXM6IGludAopIC0+IHN0cjoKICAgICIiIgogICAgVXBkYXRlIG1hbmlmZXN0X3N1bW1hcnkudG90YWxfcmVnaXN0ZXJlZF9lbnRyaWVzIHdoZW4gdGhhdCBmaWVsZCBleGlzdHMuCiAgICAiIiIKCiAgICB0cnk6CiAgICAgICAgcmV0dXJuIHJlcGxhY2VfeWFtbF9zY2FsYXJfcGF0aCgKICAgICAgICAgICAgdGV4dCwKICAgICAgICAgICAgKAogICAgICAgICAgICAgICAgIm1hbmlmZXN0X3N1bW1hcnkiLAogICAgICAgICAgICAgICAgInRvdGFsX3JlZ2lzdGVyZWRfZW50cmllcyIKICAgICAgICAgICAgKSwKICAgICAgICAgICAgdG90YWxfZW50cmllcwogICAgICAgICkKICAgIGV4Y2VwdCBWYWx1ZUVycm9yOgogICAgICAgIHJldHVybiB0ZXh0CgoKZGVmIGJ1aWxkX2ZpbGVfbWFuaWZlc3RfdGV4dCgKICAgIG1hbmlmZXN0X2NoYW5nZXM6IExpc3RbTWFuaWZlc3RFbnRyeUNoYW5nZV0sCiAgICBuZXdfZW50cnk6IE9wdGlvbmFsWwogICAgICAgIFR1cGxlWwogICAgICAgICAgICBzdHIsCiAgICAgICAgICAgIERpY3Rbc3RyLCBBbnldCiAgICAgICAgXQogICAgXQopIC0+IHN0cjoKICAgICIiIgogICAgQnVpbGQgdGhlIHN5bmNocm9uaXplZCBGaWxlIE1hbmlmZXN0IHRleHQgd2hpbGUgcHJlc2VydmluZyBjb21tZW50cy4KICAgICIiIgoKICAgIHRleHQgPSBGSUxFX01BTklGRVNULnJlYWRfdGV4dCgKICAgICAgICBlbmNvZGluZz0idXRmLTgiCiAgICApCgogICAgZm9yIGNoYW5nZSBpbiBtYW5pZmVzdF9jaGFuZ2VzOgogICAgICAgIHRleHQgPSByZXBsYWNlX21hbmlmZXN0X2VudHJ5X3N0YXR1cygKICAgICAgICAgICAgdGV4dCwKICAgICAgICAgICAgZmlsZV9pZD1jaGFuZ2UuZmlsZV9pZCwKICAgICAgICAgICAgc3RhdHVzPWNoYW5nZS5uZXdfc3RhdHVzCiAgICAgICAgKQoKICAgIGlmIG5ld19lbnRyeSBpcyBub3QgTm9uZToKCiAgICAgICAgZmlsZV9pZCwgcmVjb3JkID0gbmV3X2VudHJ5CgogICAgICAgIHRleHQgPSBpbnNlcnRfbWFuaWZlc3RfZW50cnkoCiAgICAgICAgICAgIHRleHQsCiAgICAgICAgICAgIGZpbGVfaWQ9ZmlsZV9pZCwKICAgICAgICAgICAgcmVjb3JkPXJlY29yZAogICAgICAgICkKCiAgICBwYXJzZWQgPSB5YW1sLnNhZmVfbG9hZCh0ZXh0KQoKICAgIGlmIGlzaW5zdGFuY2UocGFyc2VkLCBkaWN0KToKCiAgICAgICAgZW50cmllcyA9IGNvbGxlY3RfbWFuaWZlc3RfcmVjb3JkcyhwYXJzZWQpCgogICAgICAgIHRleHQgPSB1cGRhdGVfbWFuaWZlc3Rfc3VtbWFyeV90b3RhbCgKICAgICAgICAgICAgdGV4dCwKICAgICAgICAgICAgbGVuKGVudHJpZXMpCiAgICAgICAgKQoKICAgIHJldHVybiB0ZXh0CgoKZGVmIGxvYWRfeWFtbF90ZXh0KAogICAgdGV4dDogc3RyLAogICAgKiwKICAgIHNvdXJjZV9uYW1lOiBzdHIKKSAtPiBEaWN0W3N0ciwgQW55XToKICAgICIiIgogICAgUGFyc2UgWUFNTCB0ZXh0IGFuZCByZXF1aXJlIGEgbWFwcGluZyByb290LgogICAgIiIiCgogICAgbG9hZGVkID0geWFtbC5zYWZlX2xvYWQodGV4dCkKCiAgICBpZiBub3QgaXNpbnN0YW5jZShsb2FkZWQsIGRpY3QpOgogICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgIGYie3NvdXJjZV9uYW1lfSBtdXN0IGNvbnRhaW4gYSBtYXBwaW5nIHJvb3QuIgogICAgICAgICkKCiAgICByZXR1cm4gbG9hZGVkCgoKZGVmIGJ1aWxkX2Jhc2VsaW5lX3RleHRfdXNpbmdfbWFuaWZlc3QoCiAgICBjYW5vbmljYWxfc3RhdGU6IENhbm9uaWNhbEV4ZWN1dGlvblN0YXRlLAogICAgdXBkYXRlZF9tYW5pZmVzdDogRGljdFtzdHIsIEFueV0KKSAtPiBzdHI6CiAgICAiIiIKICAgIEJ1aWxkIEJhc2VsaW5lIE1hbmlmZXN0IHRleHQgdXNpbmcgdGhlIHN5bmNocm9uaXplZCBGaWxlIE1hbmlmZXN0CiAgICBhcyB0aGUgdGVtcG9yYXJ5IGF1dGhvcml0eS4KICAgICIiIgoKICAgIG9yaWdpbmFsX2xvYWQgPSBTYWZlWWFtbC5sb2FkCgogICAgZGVmIHRlbXBvcmFyeV9sb2FkKHBhdGg6IFBhdGgpOgoKICAgICAgICBpZiBQYXRoKHBhdGgpLnJlc29sdmUoKSA9PSBGSUxFX01BTklGRVNULnJlc29sdmUoKToKICAgICAgICAgICAgcmV0dXJuIHVwZGF0ZWRfbWFuaWZlc3QKCiAgICAgICAgcmV0dXJuIG9yaWdpbmFsX2xvYWQocGF0aCkKCiAgICBTYWZlWWFtbC5sb2FkID0gc3RhdGljbWV0aG9kKHRlbXBvcmFyeV9sb2FkKQoKICAgIHRyeToKICAgICAgICByZXR1cm4gYnVpbGRfYmFzZWxpbmVfbWFuaWZlc3RfdGV4dCgKICAgICAgICAgICAgY2Fub25pY2FsX3N0YXRlCiAgICAgICAgKQogICAgZmluYWxseToKICAgICAgICBTYWZlWWFtbC5sb2FkID0gc3RhdGljbWV0aG9kKG9yaWdpbmFsX2xvYWQpCgoKZGVmIHZhbGlkYXRlX3RocmVlX3RlbXBvcmFyeV9kb2N1bWVudHMoCiAgICBtYW5pZmVzdF90cmFuc2FjdGlvbjogVHJhbnNhY3Rpb25GaWxlLAogICAgY3VycmVudF90cmFuc2FjdGlvbjogVHJhbnNhY3Rpb25GaWxlLAogICAgYmFzZWxpbmVfdHJhbnNhY3Rpb246IFRyYW5zYWN0aW9uRmlsZSwKICAgIGRlcGVuZGVuY3lfbWFwOiBEaWN0W3N0ciwgQW55XSwKICAgIGNhbm9uaWNhbF9zdGF0ZTogQ2Fub25pY2FsRXhlY3V0aW9uU3RhdGUKKSAtPiBOb25lOgogICAgIiIiCiAgICBWYWxpZGF0ZSBzeW50YXggYW5kIHNlbWFudGljcyBmb3IgYWxsIHRocmVlIHRlbXBvcmFyeSBkb2N1bWVudHMuCiAgICAiIiIKCiAgICBmb3IgdHJhbnNhY3Rpb24gaW4gKAogICAgICAgIG1hbmlmZXN0X3RyYW5zYWN0aW9uLAogICAgICAgIGN1cnJlbnRfdHJhbnNhY3Rpb24sCiAgICAgICAgYmFzZWxpbmVfdHJhbnNhY3Rpb24KICAgICk6CiAgICAgICAgdHJhbnNhY3Rpb24udGVtcG9yYXJ5LndyaXRlX3RleHQoCiAgICAgICAgICAgIHRyYW5zYWN0aW9uLmNvbnRlbnQsCiAgICAgICAgICAgIGVuY29kaW5nPSJ1dGYtOCIKICAgICAgICApCgogICAgbWFuaWZlc3RfZG9jdW1lbnQgPSBTYWZlWWFtbC5sb2FkKAogICAgICAgIG1hbmlmZXN0X3RyYW5zYWN0aW9uLnRlbXBvcmFyeQogICAgKQoKICAgIGN1cnJlbnRfZG9jdW1lbnQgPSBTYWZlWWFtbC5sb2FkKAogICAgICAgIGN1cnJlbnRfdHJhbnNhY3Rpb24udGVtcG9yYXJ5CiAgICApCgogICAgYmFzZWxpbmVfZG9jdW1lbnQgPSBTYWZlWWFtbC5sb2FkKAogICAgICAgIGJhc2VsaW5lX3RyYW5zYWN0aW9uLnRlbXBvcmFyeQogICAgKQoKICAgIGlmIG5vdCBpc2luc3RhbmNlKG1hbmlmZXN0X2RvY3VtZW50LCBkaWN0KToKICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAiVGVtcG9yYXJ5IEZpbGUgTWFuaWZlc3QgaXMgaW52YWxpZC4iCiAgICAgICAgKQoKICAgIGlmIG5vdCBpc2luc3RhbmNlKGN1cnJlbnRfZG9jdW1lbnQsIGRpY3QpOgogICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICJUZW1wb3JhcnkgQ3VycmVudCBTdGF0ZSBpcyBpbnZhbGlkLiIKICAgICAgICApCgogICAgaWYgbm90IGlzaW5zdGFuY2UoYmFzZWxpbmVfZG9jdW1lbnQsIGRpY3QpOgogICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICJUZW1wb3JhcnkgQmFzZWxpbmUgTWFuaWZlc3QgaXMgaW52YWxpZC4iCiAgICAgICAgKQoKICAgIHZhbGlkYXRlX2ZpbGVfbWFuaWZlc3RfcmVzdWx0KAogICAgICAgIG1hbmlmZXN0X2RvY3VtZW50LAogICAgICAgIGRlcGVuZGVuY3lfbWFwCiAgICApCgogICAgdmFsaWRhdGVfY3VycmVudF9zdGF0ZV9yZXN1bHQoCiAgICAgICAgY3VycmVudF9kb2N1bWVudCwKICAgICAgICBjYW5vbmljYWxfc3RhdGUKICAgICkKCiAgICBvcmlnaW5hbF9sb2FkID0gU2FmZVlhbWwubG9hZAoKICAgIGRlZiB0ZW1wb3JhcnlfbG9hZChwYXRoOiBQYXRoKToKCiAgICAgICAgaWYgUGF0aChwYXRoKS5yZXNvbHZlKCkgPT0gRklMRV9NQU5JRkVTVC5yZXNvbHZlKCk6CiAgICAgICAgICAgIHJldHVybiBtYW5pZmVzdF9kb2N1bWVudAoKICAgICAgICByZXR1cm4gb3JpZ2luYWxfbG9hZChwYXRoKQoKICAgIFNhZmVZYW1sLmxvYWQgPSBzdGF0aWNtZXRob2QodGVtcG9yYXJ5X2xvYWQpCgogICAgdHJ5OgogICAgICAgIHZhbGlkYXRlX2Jhc2VsaW5lX21hbmlmZXN0X3Jlc3VsdCgKICAgICAgICAgICAgYmFzZWxpbmVfZG9jdW1lbnQsCiAgICAgICAgICAgIGNhbm9uaWNhbF9zdGF0ZQogICAgICAgICkKICAgIGZpbmFsbHk6CiAgICAgICAgU2FmZVlhbWwubG9hZCA9IHN0YXRpY21ldGhvZChvcmlnaW5hbF9sb2FkKQoKCmRlZiBhcHBseV90aHJlZV9maWxlX3N5bmNocm9uaXphdGlvbigKICAgICosCiAgICBkZXBlbmRlbmN5X21hcDogRGljdFtzdHIsIEFueV0sCiAgICB1cGRhdGVkX21hbmlmZXN0OiBEaWN0W3N0ciwgQW55XSwKICAgIG1hbmlmZXN0X2NoYW5nZXM6IExpc3RbTWFuaWZlc3RFbnRyeUNoYW5nZV0sCiAgICBuZXdfbWFuaWZlc3RfZW50cnk6IE9wdGlvbmFsWwogICAgICAgIFR1cGxlWwogICAgICAgICAgICBzdHIsCiAgICAgICAgICAgIERpY3Rbc3RyLCBBbnldCiAgICAgICAgXQogICAgXSwKICAgIGNhbm9uaWNhbF9zdGF0ZTogQ2Fub25pY2FsRXhlY3V0aW9uU3RhdGUsCiAgICBydW5fdmFsaWRhdG9yOiBib29sCikgLT4gaW50OgogICAgIiIiCiAgICBBcHBseSBGaWxlIE1hbmlmZXN0LCBDdXJyZW50IFN0YXRlIGFuZCBCYXNlbGluZSBNYW5pZmVzdCBhcyBvbmUKICAgIHJlY292ZXJhYmxlIHRyYW5zYWN0aW9uLgogICAgIiIiCgogICAgdGltZXN0YW1wID0gZGF0ZXRpbWUubm93KCkuc3RyZnRpbWUoCiAgICAgICAgIiVZJW0lZF8lSCVNJVMiCiAgICApCgogICAgbWFuaWZlc3RfdGV4dCA9IGJ1aWxkX2ZpbGVfbWFuaWZlc3RfdGV4dCgKICAgICAgICBtYW5pZmVzdF9jaGFuZ2VzLAogICAgICAgIG5ld19tYW5pZmVzdF9lbnRyeQogICAgKQoKICAgIGN1cnJlbnRfdGV4dCA9IGJ1aWxkX2N1cnJlbnRfc3RhdGVfdGV4dCgKICAgICAgICBjYW5vbmljYWxfc3RhdGUKICAgICkKCiAgICBiYXNlbGluZV90ZXh0ID0gYnVpbGRfYmFzZWxpbmVfdGV4dF91c2luZ19tYW5pZmVzdCgKICAgICAgICBjYW5vbmljYWxfc3RhdGUsCiAgICAgICAgdXBkYXRlZF9tYW5pZmVzdAogICAgKQoKICAgIG1hbmlmZXN0X3RyYW5zYWN0aW9uID0gY3JlYXRlX3RyYW5zYWN0aW9uX2ZpbGUoCiAgICAgICAgdGFyZ2V0PUZJTEVfTUFOSUZFU1QsCiAgICAgICAgY29udGVudD1tYW5pZmVzdF90ZXh0LAogICAgICAgIHRpbWVzdGFtcD10aW1lc3RhbXAKICAgICkKCiAgICBjdXJyZW50X3RyYW5zYWN0aW9uID0gY3JlYXRlX3RyYW5zYWN0aW9uX2ZpbGUoCiAgICAgICAgdGFyZ2V0PUNVUlJFTlRfU1RBVEUsCiAgICAgICAgY29udGVudD1jdXJyZW50X3RleHQsCiAgICAgICAgdGltZXN0YW1wPXRpbWVzdGFtcAogICAgKQoKICAgIGJhc2VsaW5lX3RyYW5zYWN0aW9uID0gY3JlYXRlX3RyYW5zYWN0aW9uX2ZpbGUoCiAgICAgICAgdGFyZ2V0PUJBU0VMSU5FX01BTklGRVNULAogICAgICAgIGNvbnRlbnQ9YmFzZWxpbmVfdGV4dCwKICAgICAgICB0aW1lc3RhbXA9dGltZXN0YW1wCiAgICApCgogICAgdHJhbnNhY3Rpb25zID0gKAogICAgICAgIG1hbmlmZXN0X3RyYW5zYWN0aW9uLAogICAgICAgIGN1cnJlbnRfdHJhbnNhY3Rpb24sCiAgICAgICAgYmFzZWxpbmVfdHJhbnNhY3Rpb24KICAgICkKCiAgICB0cnk6CiAgICAgICAgdmFsaWRhdGVfdGhyZWVfdGVtcG9yYXJ5X2RvY3VtZW50cygKICAgICAgICAgICAgbWFuaWZlc3RfdHJhbnNhY3Rpb24sCiAgICAgICAgICAgIGN1cnJlbnRfdHJhbnNhY3Rpb24sCiAgICAgICAgICAgIGJhc2VsaW5lX3RyYW5zYWN0aW9uLAogICAgICAgICAgICBkZXBlbmRlbmN5X21hcCwKICAgICAgICAgICAgY2Fub25pY2FsX3N0YXRlCiAgICAgICAgKQoKICAgICAgICBmb3IgdHJhbnNhY3Rpb24gaW4gdHJhbnNhY3Rpb25zOgogICAgICAgICAgICBzaHV0aWwuY29weTIoCiAgICAgICAgICAgICAgICB0cmFuc2FjdGlvbi50YXJnZXQsCiAgICAgICAgICAgICAgICB0cmFuc2FjdGlvbi5iYWNrdXAKICAgICAgICAgICAgKQoKICAgICAgICBmb3IgdHJhbnNhY3Rpb24gaW4gdHJhbnNhY3Rpb25zOgogICAgICAgICAgICB0cmFuc2FjdGlvbi50ZW1wb3JhcnkucmVwbGFjZSgKICAgICAgICAgICAgICAgIHRyYW5zYWN0aW9uLnRhcmdldAogICAgICAgICAgICApCgogICAgICAgIHdyaXR0ZW5fbWFuaWZlc3QgPSBTYWZlWWFtbC5sb2FkKAogICAgICAgICAgICBGSUxFX01BTklGRVNUCiAgICAgICAgKQoKICAgICAgICB3cml0dGVuX2N1cnJlbnQgPSBTYWZlWWFtbC5sb2FkKAogICAgICAgICAgICBDVVJSRU5UX1NUQVRFCiAgICAgICAgKQoKICAgICAgICB3cml0dGVuX2Jhc2VsaW5lID0gU2FmZVlhbWwubG9hZCgKICAgICAgICAgICAgQkFTRUxJTkVfTUFOSUZFU1QKICAgICAgICApCgogICAgICAgIGlmIG5vdCBpc2luc3RhbmNlKHdyaXR0ZW5fbWFuaWZlc3QsIGRpY3QpOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgIldyaXR0ZW4gRmlsZSBNYW5pZmVzdCBpcyBpbnZhbGlkLiIKICAgICAgICAgICAgKQoKICAgICAgICBpZiBub3QgaXNpbnN0YW5jZSh3cml0dGVuX2N1cnJlbnQsIGRpY3QpOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgIldyaXR0ZW4gQ3VycmVudCBTdGF0ZSBpcyBpbnZhbGlkLiIKICAgICAgICAgICAgKQoKICAgICAgICBpZiBub3QgaXNpbnN0YW5jZSh3cml0dGVuX2Jhc2VsaW5lLCBkaWN0KToKICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigKICAgICAgICAgICAgICAgICJXcml0dGVuIEJhc2VsaW5lIE1hbmlmZXN0IGlzIGludmFsaWQuIgogICAgICAgICAgICApCgogICAgICAgIHZhbGlkYXRlX2ZpbGVfbWFuaWZlc3RfcmVzdWx0KAogICAgICAgICAgICB3cml0dGVuX21hbmlmZXN0LAogICAgICAgICAgICBkZXBlbmRlbmN5X21hcAogICAgICAgICkKCiAgICAgICAgdmFsaWRhdGVfY3VycmVudF9zdGF0ZV9yZXN1bHQoCiAgICAgICAgICAgIHdyaXR0ZW5fY3VycmVudCwKICAgICAgICAgICAgY2Fub25pY2FsX3N0YXRlCiAgICAgICAgKQoKICAgICAgICBvcmlnaW5hbF9sb2FkID0gU2FmZVlhbWwubG9hZAoKICAgICAgICBkZWYgd3JpdHRlbl9tYW5pZmVzdF9sb2FkKHBhdGg6IFBhdGgpOgoKICAgICAgICAgICAgaWYgUGF0aChwYXRoKS5yZXNvbHZlKCkgPT0gRklMRV9NQU5JRkVTVC5yZXNvbHZlKCk6CiAgICAgICAgICAgICAgICByZXR1cm4gd3JpdHRlbl9tYW5pZmVzdAoKICAgICAgICAgICAgcmV0dXJuIG9yaWdpbmFsX2xvYWQocGF0aCkKCiAgICAgICAgU2FmZVlhbWwubG9hZCA9IHN0YXRpY21ldGhvZCgKICAgICAgICAgICAgd3JpdHRlbl9tYW5pZmVzdF9sb2FkCiAgICAgICAgKQoKICAgICAgICB0cnk6CiAgICAgICAgICAgIHZhbGlkYXRlX2Jhc2VsaW5lX21hbmlmZXN0X3Jlc3VsdCgKICAgICAgICAgICAgICAgIHdyaXR0ZW5fYmFzZWxpbmUsCiAgICAgICAgICAgICAgICBjYW5vbmljYWxfc3RhdGUKICAgICAgICAgICAgKQogICAgICAgIGZpbmFsbHk6CiAgICAgICAgICAgIFNhZmVZYW1sLmxvYWQgPSBzdGF0aWNtZXRob2QoCiAgICAgICAgICAgICAgICBvcmlnaW5hbF9sb2FkCiAgICAgICAgICAgICkKCiAgICAgICAgaWYgcnVuX3ZhbGlkYXRvcjoKCiAgICAgICAgICAgIHZhbGlkYXRvcl9jb2RlID0gZXhlY3V0ZV92YWxpZGF0b3JfcHJvY2VzcygpCgogICAgICAgICAgICBpZiB2YWxpZGF0b3JfY29kZSAhPSAwOgogICAgICAgICAgICAgICAgcmFpc2UgUnVudGltZUVycm9yKAogICAgICAgICAgICAgICAgICAgICJQcm9qZWN0IENvbnRyb2wgVmFsaWRhdG9yIHJldHVybmVkICIKICAgICAgICAgICAgICAgICAgICBmImV4aXQgY29kZSB7dmFsaWRhdG9yX2NvZGV9LiIKICAgICAgICAgICAgICAgICkKCiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGVycm9yOgoKICAgICAgICByZXN0b3JlX3RyYW5zYWN0aW9ucygKICAgICAgICAgICAgdHJhbnNhY3Rpb25zCiAgICAgICAgKQoKICAgICAgICBjbGVhbnVwX3RyYW5zYWN0aW9uX3RlbXBvcmFyeV9maWxlcygKICAgICAgICAgICAgdHJhbnNhY3Rpb25zCiAgICAgICAgKQoKICAgICAgICBwcmludCgpCiAgICAgICAgcHJpbnQoCiAgICAgICAgICAgICJTWU5DSFJPTklaQVRJT04gUk9MTEVEIEJBQ0siLAogICAgICAgICAgICBmaWxlPXN5cy5zdGRlcnIKICAgICAgICApCgogICAgICAgIHByaW50KAogICAgICAgICAgICBmIlJlYXNvbjoge2Vycm9yfSIsCiAgICAgICAgICAgIGZpbGU9c3lzLnN0ZGVycgogICAgICAgICkKCiAgICAgICAgcHJpbnQoCiAgICAgICAgICAgICJUaGUgdGhyZWUgdGFyZ2V0IGZpbGVzIHdlcmUgcmVzdG9yZWQuIiwKICAgICAgICAgICAgZmlsZT1zeXMuc3RkZXJyCiAgICAgICAgKQoKICAgICAgICByZXR1cm4gMgoKICAgIGNsZWFudXBfdHJhbnNhY3Rpb25fdGVtcG9yYXJ5X2ZpbGVzKAogICAgICAgIHRyYW5zYWN0aW9ucwogICAgKQoKICAgIHByaW50KCkKICAgIHByaW50KCJTWU5DSFJPTklaQVRJT04gQVBQTElFRCIpCgogICAgZm9yIHRyYW5zYWN0aW9uIGluIHRyYW5zYWN0aW9uczoKCiAgICAgICAgcHJpbnQoCiAgICAgICAgICAgIGYiVXBkYXRlZCA6IHt0cmFuc2FjdGlvbi50YXJnZXR9IgogICAgICAgICkKCiAgICAgICAgcHJpbnQoCiAgICAgICAgICAgIGYiQmFja3VwICA6IHt0cmFuc2FjdGlvbi5iYWNrdXB9IgogICAgICAgICkKCiAgICBpZiBydW5fdmFsaWRhdG9yOgoKICAgICAgICBwcmludCgpCiAgICAgICAgcHJpbnQoCiAgICAgICAgICAgICJQcm9qZWN0IENvbnRyb2wgVmFsaWRhdG9yOiBQQVNTIgogICAgICAgICkKCiAgICByZXR1cm4gMAoKCmRlZiBydW5fcGFydF9zZXZlbigKICAgIGFyZ3M6IGFyZ3BhcnNlLk5hbWVzcGFjZQopIC0+IGludDoKICAgICIiIgogICAgRXhlY3V0ZSBjb21wbGV0ZSB0aHJlZS1kb2N1bWVudCBkcnkgcnVuIG9yIHRyYW5zYWN0aW9uYWwgYXBwbGljYXRpb24uCiAgICAiIiIKCiAgICBkZXBlbmRlbmN5X21hcCA9IFNhZmVZYW1sLmxvYWQoCiAgICAgICAgREVQRU5ERU5DWV9NQVAKICAgICkKCiAgICBpZiBub3QgaXNpbnN0YW5jZShkZXBlbmRlbmN5X21hcCwgZGljdCk6CiAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigKICAgICAgICAgICAgIkNJUFNfREVQRU5ERU5DWV9NQVAueWFtbCBtdXN0IGNvbnRhaW4gYSBtYXBwaW5nIHJvb3QuIgogICAgICAgICkKCiAgICBtYW5pZmVzdF9zeW5jaHJvbml6ZXIgPSBGaWxlTWFuaWZlc3RTeW5jaHJvbml6ZXIoKQoKICAgICgKICAgICAgICB1cGRhdGVkX21hbmlmZXN0LAogICAgICAgIG1hbmlmZXN0X2NoYW5nZXMsCiAgICAgICAgbmV3X21hbmlmZXN0X2VudHJ5CiAgICApID0gbWFuaWZlc3Rfc3luY2hyb25pemVyLnN5bmNocm9uaXplKCkKCiAgICB2YWxpZGF0ZV9maWxlX21hbmlmZXN0X3Jlc3VsdCgKICAgICAgICB1cGRhdGVkX21hbmlmZXN0LAogICAgICAgIGRlcGVuZGVuY3lfbWFwCiAgICApCgogICAgY2Fub25pY2FsX3N0YXRlID0gcmVzb2x2ZV9jYW5vbmljYWxfc3RhdGUoCiAgICAgICAgZGVwZW5kZW5jeV9tYXAsCiAgICAgICAgdXBkYXRlZF9tYW5pZmVzdAogICAgKQoKICAgIHByaW50KAogICAgICAgIGYiQ3VycmVudCBwaGFzZSAgICAgICA6ICIKICAgICAgICBmIntjYW5vbmljYWxfc3RhdGUuY3VycmVudF9waGFzZX0iCiAgICApCgogICAgcHJpbnQoCiAgICAgICAgZiJDdXJyZW50IGRlbGl2ZXJhYmxlIDogIgogICAgICAgIGYie2Nhbm9uaWNhbF9zdGF0ZS5jdXJyZW50X2RlbGl2ZXJhYmxlfSIKICAgICkKCiAgICBwcmludCgKICAgICAgICBmIkxhc3QgYWNjZXB0ZWQgICAgICAgOiAiCiAgICAgICAgZiJ7Y2Fub25pY2FsX3N0YXRlLmxhc3RfYWNjZXB0ZWQgb3IgJ05PTkUnfSIKICAgICkKCiAgICBwcmludCgKICAgICAgICBmIk5leHQgZGVsaXZlcmFibGUgICAgOiAiCiAgICAgICAgZiJ7Y2Fub25pY2FsX3N0YXRlLm5leHRfZGVsaXZlcmFibGUgb3IgJ05PTkUnfSIKICAgICkKCiAgICBwcmludCgpCiAgICBwcmludCgKICAgICAgICAiQ2Fub25pY2FsIHN0YXRlIHJlc29sdmVkIGZyb20gdGhlIHN5bmNocm9uaXplZCAiCiAgICAgICAgIkZpbGUgTWFuaWZlc3QuIgogICAgKQogICAgcHJpbnQoKQoKICAgIHJlc3VsdCA9IFN5bmNocm9uaXphdGlvblJlc3VsdCgpCgogICAgKAogICAgICAgIF91cGRhdGVkX2N1cnJlbnRfc3RhdGUsCiAgICAgICAgY3VycmVudF9zdGF0ZV9jaGFuZ2VzCiAgICApID0gc3luY2hyb25pemVfY3VycmVudF9zdGF0ZSgKICAgICAgICBjYW5vbmljYWxfc3RhdGUsCiAgICAgICAgcmVzdWx0CiAgICApCgogICAgYmFzZWxpbmVfc3luY2hyb25pemVyID0gQmFzZWxpbmVNYW5pZmVzdFN5bmNocm9uaXplcigKICAgICAgICBjYW5vbmljYWxfc3RhdGUKICAgICkKCiAgICBiYXNlbGluZV9zeW5jaHJvbml6ZXIubWFuaWZlc3Rfc3RhdHVzX2J5X2ZpbGVfaWQgPSAoCiAgICAgICAgYnVpbGRfbWFuaWZlc3Rfc3RhdHVzX2luZGV4X2Zyb21fZG9jdW1lbnQoCiAgICAgICAgICAgIHVwZGF0ZWRfbWFuaWZlc3QKICAgICAgICApCiAgICApCgogICAgKAogICAgICAgIF91cGRhdGVkX2Jhc2VsaW5lLAogICAgICAgIGJhc2VsaW5lX2NoYW5nZXMKICAgICkgPSBiYXNlbGluZV9zeW5jaHJvbml6ZXIuc3luY2hyb25pemUoKQoKICAgIHByaW50X21hbmlmZXN0X2NoYW5nZV9wbGFuKAogICAgICAgIG1hbmlmZXN0X2NoYW5nZXMsCiAgICAgICAgbmV3X21hbmlmZXN0X2VudHJ5CiAgICApCgogICAgcHJpbnRfY2hhbmdlX3BsYW4oCiAgICAgICAgY3VycmVudF9zdGF0ZV9jaGFuZ2VzLAogICAgICAgIHRpdGxlPSgKICAgICAgICAgICAgIkNJUFNfQ1VSUkVOVF9TVEFURS55YW1sICIKICAgICAgICAgICAgIlN5bmNocm9uaXphdGlvbiBQbGFuIgogICAgICAgICkKICAgICkKCiAgICBwcmludF9jaGFuZ2VfcGxhbigKICAgICAgICBiYXNlbGluZV9jaGFuZ2VzLAogICAgICAgIHRpdGxlPSgKICAgICAgICAgICAgIkNJUFNfQkFTRUxJTkVfTUFOSUZFU1QueWFtbCAiCiAgICAgICAgICAgICJTeW5jaHJvbml6YXRpb24gUGxhbiIKICAgICAgICApCiAgICApCgogICAgdG90YWxfY2hhbmdlcyA9ICgKICAgICAgICBsZW4obWFuaWZlc3RfY2hhbmdlcykKICAgICAgICArICgKICAgICAgICAgICAgMQogICAgICAgICAgICBpZiBuZXdfbWFuaWZlc3RfZW50cnkgaXMgbm90IE5vbmUKICAgICAgICAgICAgZWxzZSAwCiAgICAgICAgKQogICAgICAgICsgbGVuKGN1cnJlbnRfc3RhdGVfY2hhbmdlcykKICAgICAgICArIGxlbihiYXNlbGluZV9jaGFuZ2VzKQogICAgKQoKICAgIHByaW50KAogICAgICAgIGYiVG90YWwgcHJvcG9zZWQgY2hhbmdlczogIgogICAgICAgIGYie3RvdGFsX2NoYW5nZXN9IgogICAgKQogICAgcHJpbnQoKQoKICAgIGlmIG5vdCBhcmdzLmFwcGx5OgoKICAgICAgICBwcmludCgKICAgICAgICAgICAgIkRSWSBSVU4gY29tcGxldGVkLiAiCiAgICAgICAgICAgICJObyByZXBvc2l0b3J5IGZpbGVzIHdlcmUgbW9kaWZpZWQuIgogICAgICAgICkKCiAgICAgICAgcmV0dXJuIDAKCiAgICBpZiB0b3RhbF9jaGFuZ2VzID09IDA6CgogICAgICAgIHByaW50KAogICAgICAgICAgICAiTm8gc3luY2hyb25pemF0aW9uIGNoYW5nZXMgYXJlIHJlcXVpcmVkLiIKICAgICAgICApCgogICAgICAgIGlmIGFyZ3MudmFsaWRhdGU6CgogICAgICAgICAgICB2YWxpZGF0b3JfY29kZSA9IGV4ZWN1dGVfdmFsaWRhdG9yX3Byb2Nlc3MoKQoKICAgICAgICAgICAgaWYgdmFsaWRhdG9yX2NvZGUgIT0gMDoKICAgICAgICAgICAgICAgIHJldHVybiAyCgogICAgICAgICAgICBwcmludCgKICAgICAgICAgICAgICAgICJQcm9qZWN0IENvbnRyb2wgVmFsaWRhdG9yOiBQQVNTIgogICAgICAgICAgICApCgogICAgICAgIHJldHVybiAwCgogICAgcmV0dXJuIGFwcGx5X3RocmVlX2ZpbGVfc3luY2hyb25pemF0aW9uKAogICAgICAgIGRlcGVuZGVuY3lfbWFwPWRlcGVuZGVuY3lfbWFwLAogICAgICAgIHVwZGF0ZWRfbWFuaWZlc3Q9dXBkYXRlZF9tYW5pZmVzdCwKICAgICAgICBtYW5pZmVzdF9jaGFuZ2VzPW1hbmlmZXN0X2NoYW5nZXMsCiAgICAgICAgbmV3X21hbmlmZXN0X2VudHJ5PW5ld19tYW5pZmVzdF9lbnRyeSwKICAgICAgICBjYW5vbmljYWxfc3RhdGU9Y2Fub25pY2FsX3N0YXRlLAogICAgICAgIHJ1bl92YWxpZGF0b3I9Ym9vbCgKICAgICAgICAgICAgYXJncy52YWxpZGF0ZQogICAgICAgICkKICAgICkKCgojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiMgRU5EIE9GIFBBUlQgVklJCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0K"


def main() -> int:

    script_directory = Path(__file__).resolve().parent
    target = script_directory / TARGET_NAME

    if not target.is_file():

        print(
            f"ERROR: File not found: {target}",
            file=sys.stderr
        )

        return 2

    original = target.read_text(
        encoding="utf-8"
    )

    if "def run_part_seven(" in original:

        print("NO CHANGES REQUIRED")
        print("Part VII is already installed.")

        return 0

    if "def run_part_six(" not in original:

        print(
            "ERROR: Part VI was not found.",
            file=sys.stderr
        )

        return 3

    call_pattern = re.compile(
        r"exit_code\s*=\s*run_part_six\(args\)"
    )

    if len(
        call_pattern.findall(
            original
        )
    ) != 1:

        print(
            "ERROR: Expected exactly one "
            "run_part_six(args) call.",
            file=sys.stderr
        )

        return 4

    entry_pattern = re.compile(
        r'\nif __name__ == "__main__":\s*'
        r'\n\s*raise SystemExit\(\s*'
        r'\n\s*main\(\)\s*'
        r'\n\s*\)\s*',
        re.MULTILINE
    )

    entry_matches = list(
        entry_pattern.finditer(
            original
        )
    )

    if len(entry_matches) != 1:

        print(
            "ERROR: Expected exactly one script entry point.",
            file=sys.stderr
        )

        return 5

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = target.with_name(
        f"{target.name}.bak_part7_{timestamp}"
    )

    shutil.copy2(
        target,
        backup
    )

    if not re.search(
        r"^import re$",
        original,
        flags=re.MULTILINE
    ):

        import_anchor = re.search(
            r"^import argparse$",
            original,
            flags=re.MULTILINE
        )

        if import_anchor is None:

            print(
                "ERROR: Import section could not be located.",
                file=sys.stderr
            )

            return 6

        insert_at = import_anchor.end()

        original = (
            original[:insert_at]
            + "\nimport re"
            + original[insert_at:]
        )

    updated = call_pattern.sub(
        "exit_code = run_part_seven(args)",
        original,
        count=1
    )

    entry_match = entry_pattern.search(
        updated
    )

    if entry_match is None:

        print(
            "ERROR: Entry point could not be relocated.",
            file=sys.stderr
        )

        return 7

    without_entry = (
        updated[:entry_match.start()]
        + updated[entry_match.end():]
    )

    part_code = base64.b64decode(
        PART_CODE_B64.encode("ascii")
    ).decode("utf-8")

    final_entry = """

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
"""

    assembled = (
        without_entry.rstrip()
        + "\n"
        + part_code.rstrip()
        + "\n"
        + final_entry
    )

    target.write_text(
        assembled,
        encoding="utf-8"
    )

    verification = target.read_text(
        encoding="utf-8"
    )

    required = (
        "def build_file_manifest_text(",
        "def validate_three_temporary_documents(",
        "def apply_three_file_synchronization(",
        "def run_part_seven(",
        "exit_code = run_part_seven(args)",
    )

    missing = [
        marker
        for marker in required
        if marker not in verification
    ]

    entry_count = verification.count(
        'if __name__ == "__main__":'
    )

    import_re_count = len(
        re.findall(
            r"^import re$",
            verification,
            flags=re.MULTILINE
        )
    )

    if (
        missing
        or entry_count != 1
        or import_re_count != 1
    ):

        shutil.copy2(
            backup,
            target
        )

        print(
            "PATCH ROLLED BACK",
            file=sys.stderr
        )

        if missing:

            print(
                "Missing markers: "
                + ", ".join(missing),
                file=sys.stderr
            )

        if entry_count != 1:

            print(
                f"Entry point count: {entry_count}",
                file=sys.stderr
            )

        if import_re_count != 1:

            print(
                f"import re count: {import_re_count}",
                file=sys.stderr
            )

        return 8

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Part VII installed:")
    print("- Three-file transaction")
    print("- File Manifest text-preserving writer")
    print("- Current State transactional update")
    print("- Baseline Manifest transactional update")
    print("- Temporary-file validation")
    print("- Automatic rollback")
    print("- --apply enabled")
    print("- --apply --validate enabled")
    print("- import re verified")
    print()
    print("No YAML files were modified.")
    print()
    print("Next safe command:")
    print("python -B sync_project_control.py")
    print()
    print("Confirm the DRY RUN before using --apply.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())