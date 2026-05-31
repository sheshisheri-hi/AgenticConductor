"""Sample application using vulnerable dependencies.

This file is intentionally left with known-vulnerable imports so the
mock Snyk scanner has real findings to report.

Vulnerabilities in requirements_vulnerable.txt:
  - requests==2.18.0  → CVE-2023-32681 (SSRF via Proxy-Authorization leak)
  - flask==0.12.4     → CVE-2023-30861 (cookie samesite bypass)
"""

import requests  # noqa: S113  (vulnerable version)
from flask import Flask, request

app = Flask(__name__)


@app.route("/fetch")
def fetch_url():
    """Fetches a URL — vulnerable to SSRF via requests 2.18.0."""
    target = request.args.get("url", "")
    # No SSRF validation — agent should recommend adding allowlist check
    response = requests.get(target, timeout=10)
    return response.text


if __name__ == "__main__":
    app.run(debug=True)
