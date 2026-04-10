from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()


def _pdf_text(document) -> str:
    return chr(12).join(page.get_text() for page in document)


@app.post("/extraparser/pdf2txt", response_class=PlainTextResponse)
async def pdf2txt(request: Request) -> str:
    """Extract text from a raw PDF request body."""
    try:
        import pymupdf
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="Not Implemented. If you're working on programatic integrations, skip this tool.",
        ) from exc

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="send a PDF request body")

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="request body must be a PDF")

    try:
        with pymupdf.open(stream=body, filetype="pdf") as document:
            return _pdf_text(document)
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid PDF payload") from exc
