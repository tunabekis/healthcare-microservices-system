# Healthcare Microservices System

A microservices-based healthcare system built to demonstrate independent,
decoupled services communicating over REST. Three backend services —
**Patient**, **Appointment**, and **Billing** — each own their own SQLite
database, and a Streamlit dashboard acts as the client-facing entry point.

## Architecture

```
                 ┌─────────────────────┐
                 │   Frontend (8501)    │
                 │  Streamlit Dashboard │
                 └──────────┬───────────┘
                             │ REST/JSON
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                     ▼
┌───────────────┐   ┌────────────────────┐   ┌────────────────┐
│ Patient Service│  │ Appointment Service │   │ Billing Service │
│    (8001)      │◀─│      (8002)         │──▶│     (8003)      │
└───────┬────────┘   └──────────┬──────────┘   └────────┬────────┘
        │                       │                        │
        ▼                       ▼                        ▼
   patients.db            appointments.db             billing.db
```

- **Patient Service** — registration, login, and patient lookup.
- **Appointment Service** — books appointments; validates the patient via a
  synchronous GET to the Patient Service, and triggers invoice creation via
  a POST to the Billing Service.
- **Billing Service** — generates and tracks invoices, and marks them PAID.
- **Frontend** — a Streamlit app that lets a patient register/log in, book
  appointments, view history, and pay bills.

Each service is fully isolated: its own directory, its own `main.py`, and
its own SQLite database. No code or data is shared between services.

## Tech Stack

- **Python 3.12**
- **FastAPI** + **Uvicorn** — backend microservices (ASGI)
- **Streamlit** — frontend dashboard
- **SQLite** — per-service data persistence
- **Requests** — inter-service HTTP calls

## Project Structure

```
healthcare-microservices-system/
├── patient_service/
│   └── main.py
├── appointment_service/
│   └── main.py
├── billing_service/
│   └── main.py
├── frontend/
│   └── app.py
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## Running the System

Each service runs on its own port and must be started separately (four
terminals). SQLite database files are created automatically on first run.

```bash
# Terminal 1
cd patient_service
uvicorn main:app --port 8001

# Terminal 2
cd appointment_service
uvicorn main:app --port 8002

# Terminal 3
cd billing_service
uvicorn main:app --port 8003

# Terminal 4
cd frontend
streamlit run app.py
```

Then open the Streamlit URL printed in Terminal 4 (defaults to
`http://localhost:8501`).

## API Overview

**Patient Service** (`:8001`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/register` | Create a patient account |
| POST | `/login` | Authenticate a patient |
| GET | `/patients/{patient_id}` | Fetch a patient's profile |

**Appointment Service** (`:8002`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/appointments/` | Book an appointment (validates patient, triggers billing) |
| GET | `/appointments/history/{patient_id}` | All appointments for a patient |
| GET | `/appointments/past/{patient_id}` | Past appointments |
| GET | `/appointments/upcoming/{patient_id}` | Upcoming appointments |

**Billing Service** (`:8003`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/bills/generate?patient_id=` | Generate a pending bill |
| GET | `/bills/{patient_id}` | All bills for a patient |
| GET | `/bills/pending/{patient_id}` | Unpaid bills |
| GET | `/bills/paid/{patient_id}` | Paid bills |
| POST | `/bills/pay` | Mark a bill as paid |

## Design Notes

- **Isolated data per service**: each service owns its SQLite database
  exclusively, avoiding shared-database coupling.
- **Synchronous inter-service calls**: the Appointment Service calls the
  Patient Service (validation) and Billing Service (invoicing) over HTTP,
  demonstrating the request/response side of the microservices pattern.
  A billing outage does not roll back a successful booking — bill
  generation is best-effort.
- **Passwords are hashed** (SHA-256) before being stored.
- In production, this would run behind Docker Compose / Kubernetes with an
  API gateway, rather than four manually started local processes.
