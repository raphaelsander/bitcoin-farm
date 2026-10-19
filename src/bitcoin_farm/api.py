import os
import logging
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .config import Config
from .generation import GenerationWorker
from .indexer import Indexer


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
)


class _HealthAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/health" not in message


logging.getLogger("uvicorn.access").addFilter(_HealthAccessFilter())


def _config_from_environment() -> Config:
    return Config(
        rpc_url=os.getenv("BITCOIN_RPC_URL", "http://bitcoin:8332"),
        rpc_user=os.getenv("BITCOIN_RPC_USER", "indexer"),
        rpc_password=os.getenv("BITCOIN_RPC_PASSWORD", ""),
        db_path=os.getenv("INDEXER_DB_PATH", "/data/addresses.rocksdb"),
        workers=int(os.getenv("INDEXER_WORKERS", "4")),
        rocksdb_threads=int(os.getenv("INDEXER_ROCKSDB_THREADS", "2")),
        batch_size=int(os.getenv("INDEXER_BATCH_SIZE", "100")),
        poll_interval=float(os.getenv("INDEXER_POLL_INTERVAL", "5")),
        prune_margin=int(os.getenv("INDEXER_PRUNE_MARGIN", "1000")),
        prune_interval=int(os.getenv("INDEXER_PRUNE_INTERVAL", "500")),
        start_height=int(os.getenv("INDEXER_START_HEIGHT", "0")),
        rocksdb_max_open_files=int(os.getenv("INDEXER_MAX_OPEN_FILES", "256")),
    )


class GenerationStart(BaseModel):
    filename: str


indexer: Indexer | None = None
worker: GenerationWorker | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global indexer, worker
    indexer = Indexer(_config_from_environment())
    worker = GenerationWorker(
        indexer.db,
        os.getenv("WORDLIST_DIR", "/wordlists"),
        os.getenv("WORDLIST_ENCODING", "auto"),
    )
    logging.info("Application started; starting background indexing.")
    thread = threading.Thread(target=indexer.run, name="indexer", daemon=True)
    thread.start()
    yield
    if worker is not None:
        worker.stop()
    if indexer is not None:
        indexer.close()
    logging.info("Application stopped.")


app = FastAPI(title="Bitcoin Farm API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "indexer": "running"}


@app.get("/api/addresses/{address}")
def lookup_address(address: str) -> dict:
    if indexer is None:
        raise HTTPException(status_code=503, detail="Application is not initialized yet.")
    return {
        "address": address,
        "found": indexer.db.exists(address),
        "indexed_height": indexer.db.last_height(),
    }


@app.get("/api/generation/records")
def generation_records(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    if indexer is None:
        raise HTTPException(status_code=503, detail="Application is not initialized yet.")
    return indexer.db.generated_records(offset=offset, limit=limit)


@app.delete("/api/generation/records")
def delete_generation_records(
    run_id: str | None = Query(default=None, min_length=1),
) -> dict:
    if indexer is None:
        raise HTTPException(status_code=503, detail="Application is not initialized yet.")
    try:
        deleted = indexer.db.delete_generated_records(run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": deleted, "run_id": run_id}


@app.post("/api/generation/start", status_code=202)
def start_generation(request: GenerationStart) -> dict:
    if worker is None:
        raise HTTPException(status_code=503, detail="Application is not initialized yet.")
    try:
        return worker.start(request.filename)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=409 if isinstance(exc, RuntimeError) else 400, detail=str(exc)) from exc


@app.get("/api/generation/status")
def generation_status() -> dict:
    if worker is None:
        return {"state": "starting"}
    return worker.status.snapshot()


@app.post("/api/generation/stop")
def stop_generation() -> dict:
    if worker is None:
        return {"state": "starting"}
    return worker.stop()