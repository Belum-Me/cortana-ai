"""
Servidor FastAPI de Cortana.
Expone la IA como API REST para que la app del celular se conecte.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.memory import init_db, get_recent_history
from core.llm import chat

app = FastAPI(title="Cortana API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class MessageRequest(BaseModel):
    text: str


class MessageResponse(BaseModel):
    response: str
    status: str = "ok"


@app.get("/")
def root():
    return {"status": "Cortana activa", "version": "1.0.0"}


@app.post("/chat", response_model=MessageResponse)
def chat_endpoint(req: MessageRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Mensaje vacio")
    try:
        response = chat(req.text.strip())
        return MessageResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
def get_history(limit: int = 20):
    history = get_recent_history(limit)
    return {"history": history, "count": len(history)}


@app.get("/health")
def health():
    from tools.datetime_tool import get_current_datetime
    return {"status": "ok", "time": get_current_datetime()}
