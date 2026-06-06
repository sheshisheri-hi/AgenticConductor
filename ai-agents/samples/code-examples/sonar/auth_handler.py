"""Sample auth handler with real security issues.

Issues present (for Sonar mock scanner):
  1. SQL injection at line 28 — string concatenation in query
  2. Hardcoded credential at line 14
  3. Missing input validation before DB query
"""

import sqlite3

DB_PATH = "users.db"

# ISSUE: hardcoded credential — should be loaded from env/vault
ADMIN_PASSWORD = "admin123"  # noqa: S105


def get_user(username: str) -> dict | None:
    """Fetch user by username from the database.

    ISSUE: SQL injection — username is concatenated directly into query.
    Fix: use parameterized query: cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # VULNERABILITY: direct string concatenation → SQL injection
    query = "SELECT * FROM users WHERE username='" + username + "'"
    cursor.execute(query)
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "email": row[2]}
    return None


def authenticate(username: str, password: str) -> bool:
    """Authenticate user against hardcoded admin or DB lookup."""
    if username == "admin" and password == ADMIN_PASSWORD:
        return True
    user = get_user(username)
    # ISSUE: null dereference if user is None
    return user["password_hash"] == password
