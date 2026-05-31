"""Sample code with GPL-licensed dependency.

Issues present (for BlackDuck mock scanner):
  - Direct import of a GPL-3.0-only licensed library (pypdf2 → GPL-3.0)
  - Would create copyleft obligation in commercial software
"""

# ISSUE: pypdf2 is GPL-3.0 — using it in a commercial product creates
# copyleft obligations. Recommend replacing with pypdf (Apache-2.0) or
# reportlab (commercial license).
try:
    from PyPDF2 import PdfReader  # type: ignore  # noqa: F401
except ImportError:
    PdfReader = None  # type: ignore


def extract_text_from_pdf(path: str) -> str:
    """Extract text from a PDF file using PyPDF2 (GPL-3.0)."""
    if PdfReader is None:
        return ""
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)
