from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import OCRAGENT_HOST, OCRAGENT_PORT
from .logger import get_logger

app = FastAPI(title="OCRAgent")


@app.middleware("http")
async def return_not_implemented(request: Request, call_next) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "detail": "Not Implemented. Use `ocragent tool` as the primary integration entrypoint.",
            "path": request.url.path,
            "method": request.method,
        },
    )


def serve(*, host: str = OCRAGENT_HOST, port: int = OCRAGENT_PORT) -> None:
    logger = get_logger("web")
    logger.info("Starting OCRAgent web shell on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    serve()
