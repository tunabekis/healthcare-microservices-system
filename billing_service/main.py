"""Billing Service.

Owns invoices: generation and payment status. Persists to its own
SQLite database (billing.db), isolated from every other service in
the system. Bill generation is triggered by the Appointment Service.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Billing Service")

DB_PATH = os.path.join(os.path.dirname(__file__), "billing.db")

# Flat fee simulated for every generated bill; a real system would price
# this per appointment type.
DEFAULT_BILL_AMOUNT = 150.0


@contextmanager
def get_db_connection():
    """Yield a SQLite connection and guarantee it is closed afterwards."""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS bills (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   patient_id INTEGER NOT NULL,
                   amount REAL NOT NULL,
                   status TEXT NOT NULL,
                   date_generated TEXT NOT NULL
               )"""
        )
        conn.commit()


init_db()


class PayBillRequest(BaseModel):
    bill_id: int


def _rows_to_bills(rows) -> list[dict]:
    return [{"id": r[0], "amount": r[1], "status": r[2], "date": r[3]} for r in rows]


@app.post("/bills/generate")
def generate_bill(patient_id: int):
    """Create a PENDING bill for a patient, e.g. after an appointment is booked."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO bills (patient_id, amount, status, date_generated) VALUES (?, ?, ?, ?)",
                (patient_id, DEFAULT_BILL_AMOUNT, "PENDING", today),
            )
            conn.commit()
        return {"message": "Bill generated"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/bills/{patient_id}")
def get_bills(patient_id: int):
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, amount, status, date_generated FROM bills WHERE patient_id=?",
                (patient_id,),
            ).fetchall()
        return _rows_to_bills(rows)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/bills/pending/{patient_id}")
def get_pending_bills(patient_id: int):
    """Return only pending (unpaid) bills."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, amount, status, date_generated FROM bills WHERE patient_id=? AND status='PENDING'",
                (patient_id,),
            ).fetchall()
        return _rows_to_bills(rows)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/bills/paid/{patient_id}")
def get_paid_bills(patient_id: int):
    """Return only paid bills."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, amount, status, date_generated FROM bills WHERE patient_id=? AND status='PAID'",
                (patient_id,),
            ).fetchall()
        return _rows_to_bills(rows)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/bills/pay")
def pay_bill(req: PayBillRequest):
    """Mark a bill as PAID. Fails with 404 if the bill does not exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "UPDATE bills SET status='PAID' WHERE id=?", (req.bill_id,)
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Bill not found")
        return {"message": "Bill paid successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
