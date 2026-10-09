"""Tiny dependency-free text PDF writer (used to generate the sample bank statement PDF)."""
from __future__ import annotations

from typing import List, Sequence


def _esc(s: str) -> bytes:
    return s.encode("latin-1", "replace").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def build_text_pdf(lines: Sequence[str], lines_per_page: int = 48, font_size: int = 9) -> bytes:
    pages = [list(lines[i:i + lines_per_page]) for i in range(0, len(lines), lines_per_page)] or [[]]
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs: List[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>",
                         f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
                         b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    lead = font_size + 2
    for i, pl in enumerate(pages):
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 3 0 R >> >> "
                     f"/Contents {5 + 2 * i} 0 R >>").encode())
        body = f"BT\n/F1 {font_size} Tf\n{lead} TL\n30 565 Td\n".encode()
        for ln in pl:
            body += b"(" + _esc(ln) + b") Tj\nT*\n"
        body += b"ET"
        objs.append(b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n" + body + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
