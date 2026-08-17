"""Patient Service.

Owns patient identity: registration, login, and profile lookup.
Persists to its own SQLite database (patients.db), isolated from
every other service in the system.
"""

import hashlib
import os
import sqlite3
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Patient Service")

DB_PATH = os.path.join(os.path.dirname(__file__), "patients.db")


@contextmanager
def get_db_connection():
    """Yield a SQLite connection and guarantee it is closed afterwards."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS patients (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT UNIQUE NOT NULL,
                   age INTEGER,
                   password_hash TEXT NOT NULL
               )"""
        )
        conn.commit()


init_db()


def hash_password(password: str) -> str:
    """Hash a plaintext password with SHA-256 before storing/comparing it."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class RegisterRequest(BaseModel):
    name: str
    age: int
    password: str


class LoginRequest(BaseModel):
    name: str
    password: str


@app.post("/register")
def register(req: RegisterRequest):
    with get_db_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO patients (name, age, password_hash) VALUES (?, ?, ?)",
                (req.name, req.age, hash_password(req.password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Name already registered")
        return {"message": "Registered successfully", "id": cursor.lastrowid}


@app.post("/login")
def login(req: LoginRequest):
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name FROM patients WHERE name=? AND password_hash=?",
            (req.name, hash_password(req.password)),
        )
        user = cursor.fetchone()

    if user:
        return {"id": user[0], "name": user[1]}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/patients/{patient_id}")
def get_patient(patient_id: int):
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, age FROM patients WHERE id=?", (patient_id,)
        )
        patient = cursor.fetchone()

    if patient:
        return {"id": patient[0], "name": patient[1], "age": patient[2]}
    raise HTTPException(status_code=404, detail="Patient not found")
