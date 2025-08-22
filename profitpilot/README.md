# ProfitPilotAI

Single-repo app: FastAPI backend + React (Vite) frontend. Frontend is built and static files are served by FastAPI.

## Local dev

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
