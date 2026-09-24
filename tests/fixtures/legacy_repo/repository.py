"""SQLite calls; the fixture is analyzed without executing these functions."""
import sqlite3


def save_claim(customer_id, amount):
    with sqlite3.connect("claims.db") as connection:
        cursor = connection.execute(
            "INSERT INTO claims (customer_id, amount) VALUES (?, ?)",
            (customer_id, amount),
        )
        return cursor.lastrowid


def find_claim(claim_id):
    with sqlite3.connect("claims.db") as connection:
        return connection.execute(
            "SELECT id, customer_id, amount FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
