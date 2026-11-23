from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from . import db, llm  # noqa: E402  (setelah load_dotenv)
from .schemas import TicketIn, TicketOut  # noqa: E402

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="TiketCerdas", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/tickets", response_model=TicketOut)
def create_ticket(body: TicketIn):
    try:
        result = llm.classify_ticket(body.text)
    except Exception as e:  # error API / jaringan / key salah
        raise HTTPException(status_code=502, detail=f"Gagal memanggil LLM: {e}")
    return db.insert_ticket(body.text, result)


@app.get("/api/tickets", response_model=list[TicketOut])
def get_tickets():
    return db.list_tickets()


@app.get("/api/health")
def health():
    return {"provider": llm.PROVIDER, "model": llm.model_name()}
