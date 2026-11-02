# Clinician scheduling system

A minimal full-stack scheduling application with a React frontend and FastAPI
backend. Schedule data is stored in backend memory: it survives frontend refreshes
but is cleared whenever the backend restarts.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 7, JavaScript, CSS, Fetch API |
| Backend | Python 3.11, FastAPI, Pydantic, Uvicorn |
| Storage | Thread-safe in-process memory |
| Verification | Pytest, HTTPX, Vite production build |

## Functionality

- Create appointments for Dr. Smith or Dr. Lee.
- Select start times in 15-minute increments (`:00`, `:15`, `:30`, or `:45`).
- Select a duration of 30 or 60 minutes.
- Prevent overlapping appointments for the same doctor while allowing simultaneous
  appointments for different doctors.
- Display schedules in chronological order and filter them by doctor.
- Reschedule an appointment by changing its clinician, start time, or duration.
- Cancel an appointment and immediately free its time slot.
- Preserve appointments across frontend refreshes while the backend remains running.

## Project structure

```text
backend/
  main.py             FastAPI application and in-memory schedule store
  test_main.py        API and scheduling-rule tests
  requirements.txt    Python dependencies
frontend/
  src/App.jsx         Scheduling UI and API interactions
  src/styles.css      Application styling
  vite.config.js      Development proxy configuration
```

## Launch the full-stack system

Prerequisites: Python 3.11+ and Node.js with npm. The commands below use
PowerShell and assume the terminal starts in the repository root.

### 1. Start the backend

The environment creation and dependency installation commands are only required
the first time.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Keep this terminal running. The API is available at `http://localhost:8000`, and
interactive API documentation is available at `http://localhost:8000/docs`.

### 2. Start the frontend

Open a second PowerShell terminal in the repository root:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173`. Vite proxies frontend `/api` requests to the backend
on port 8000.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check backend health |
| `GET` | `/api/clinicians` | List supported clinicians |
| `GET` | `/api/schedules` | List schedules chronologically |
| `POST` | `/api/schedules` | Create an appointment |
| `PATCH` | `/api/schedules/{schedule_id}` | Reschedule an appointment |
| `DELETE` | `/api/schedules/{schedule_id}` | Cancel an appointment |

## Verification

Run backend tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Run the frontend production build from a separate terminal or after returning to
the repository root:

```powershell
cd frontend
npm.cmd run build
```

