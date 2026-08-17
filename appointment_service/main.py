"""Appointment Service.

Owns doctor/time-slot booking. Demonstrates inter-service orchestration:
it validates the patient against the Patient Service before booking, and
triggers invoice creation on the Billing Service afterwards. Persists to
its own SQLite database (appointments.db), isolated from every other
service in the system.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Appointment Service")

PATIENT_SERVICE_URL = "http://127.0.0.1:8001/patients"
BILLING_SERVICE_URL = "http://127.0.0.1:8003"
SERVICE_CALL_TIMEOUT_SECONDS = 5

DB_PATH = os.path.join(os.path.dirname(__file__), "appointments.db")


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
            """CREATE TABLE IF NOT EXISTS appointments (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   patient_id INTEGER NOT NULL,
                   doctor TEXT NOT NULL,
                   date TEXT NOT NULL,
                   time_slot TEXT NOT NULL
               )"""
        )
        conn.commit()


init_db()


class AppointmentRequest(BaseModel):
    patient_id: int
    doctor: str
    date: str
    time_slot: str


def patient_exists(patient_id: int) -> bool:
    """Validate the patient against the Patient Service (Sync REST GET)."""
    try:
        response = requests.get(
            f"{PATIENT_SERVICE_URL}/{patient_id}", timeout=SERVICE_CALL_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Patient Service is unreachable")
    return response.status_code == 200


def trigger_bill_generation(patient_id: int) -> None:
    """Best-effort call to the Billing Service (Sync REST POST)."""
    try:
        requests.post(
            f"{BILLING_SERVICE_URL}/bills/generate",
            params={"patient_id": patient_id},
            timeout=SERVICE_CALL_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException:
        # The appointment itself already succeeded; a billing outage should
        # not roll it back. The failure is swallowed intentionally here.
        pass


@app.post("/appointments/")
def create_appointment(appt: AppointmentRequest):
    if not patient_exists(appt.patient_id):
        raise HTTPException(status_code=400, detail="Patient validation failed")

    with get_db_connection() as conn:
        conflict = conn.execute(
            "SELECT id FROM appointments WHERE doctor=? AND date=? AND time_slot=?",
            (appt.doctor, appt.date, appt.time_slot),
        ).fetchone()

        if conflict:
            raise HTTPException(status_code=400, detail="This slot is already booked!")

        conn.execute(
            "INSERT INTO appointments (patient_id, doctor, date, time_slot) VALUES (?, ?, ?, ?)",
            (appt.patient_id, appt.doctor, appt.date, appt.time_slot),
        )
        conn.commit()

    trigger_bill_generation(appt.patient_id)
    return {"message": "Appointment booked successfully"}


def _rows_to_appointments(rows) -> list[dict]:
    return [{"doctor": r[0], "date": r[1], "time": r[2]} for r in rows]


@app.get("/appointments/history/{patient_id}")
def get_history(patient_id: int):
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT doctor, date, time_slot FROM appointments WHERE patient_id=?",
                (patient_id,),
            ).fetchall()
        return _rows_to_appointments(rows)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/appointments/past/{patient_id}")
def get_past_appointments(patient_id: int):
    """Return only past appointments (date < today)."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT doctor, date, time_slot FROM appointments
                   WHERE patient_id=? AND date < ? ORDER BY date DESC""",
                (patient_id, today),
            ).fetchall()
        return _rows_to_appointments(rows)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/appointments/upcoming/{patient_id}")
def get_upcoming_appointments(patient_id: int):
    """Return only upcoming appointments (date >= today)."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT doctor, date, time_slot FROM appointments
                   WHERE patient_id=? AND date >= ? ORDER BY date ASC""",
                (patient_id, today),
            ).fetchall()
        return _rows_to_appointments(rows)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
