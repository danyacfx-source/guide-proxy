"""guide.dendich.online — static mirror of wardogs.zone/ru."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["guide.dendich.online", "localhost", "127.0.0.1"],
)


@app.middleware("http")
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.get("/api/health")
async def health():
    return {"ok": True, "static": STATIC_DIR.exists()}


@app.get("/")
async def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    ru = STATIC_DIR / "ru" / "index.html"
    if ru.exists():
        return FileResponse(ru)
    return Response("mirror not built", status_code=404)


# Clean URLs: /ru -> /ru/index.html, /ru/calculators/rewards -> .../index.html
@app.api_route("/{path:path}", methods=["GET", "HEAD"])
async def serve(path: str):
    # direct file
    candidate = STATIC_DIR / path
    if candidate.is_file():
        return FileResponse(candidate)
    # directory with index
    if candidate.is_dir():
        idx = candidate / "index.html"
        if idx.exists():
            return FileResponse(idx)
    # extensionless -> index.html
    if not Path(path).suffix:
        idx = STATIC_DIR / path / "index.html"
        if idx.exists():
            return FileResponse(idx)
        # /ru -> /ru/index.html (path without trailing slash)
        html = STATIC_DIR / (path + ".html")
        if html.exists():
            return FileResponse(html)
    return Response("not found", status_code=404)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8237, server_header=False)
