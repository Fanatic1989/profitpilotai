from fastapi import FastAPI

app = FastAPI(title="ProfitPilotAI", version="0.1")

@app.get("/health")
def health():
    return {"status": "ok", "service": "profitpilotai"}

if __name__ == "__main__":
    import os, uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
