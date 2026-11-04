import html
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import bootstrap, services, settings
from .db import engine
from .deps import LoginRequired, PasswordChangeRequired
from .routers import admin, auth, home

@asynccontextmanager
async def lifespan(_app):
    # Pilot setup: create any missing tables at start-up (safe to repeat). Alembic migrations replace this later.
    from . import models  # noqa: F401
    from .db import Base
    Base.metadata.create_all(engine)
    try:
        print("bootstrap:", bootstrap.from_env())
    except Exception as e:   # never block start-up (e.g. weak password in env var); the message shows in Render logs
        print("bootstrap failed:", e)
    yield


app = FastAPI(title=settings.APP_NAME, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="fcm_session",
                   max_age=settings.SESSION_HOURS * 3600, same_site="lax", https_only=settings.COOKIE_SECURE)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'",
        "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
        "Cache-Control": "no-store" if not request.url.path.startswith("/static") else "public, max-age=3600",
    })
    if settings.COOKIE_SECURE:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(LoginRequired)
async def _login_required(request, exc):
    return RedirectResponse("/login", 303)


@app.exception_handler(PasswordChangeRequired)
async def _pw_required(request, exc):
    return RedirectResponse("/account/password", 303)


@app.exception_handler(services.Denied)
async def _denied(request, exc):
    return HTMLResponse(f"<h3>Not permitted</h3><p>{html.escape(str(exc))}</p><p><a href='/'>Home</a></p>", status_code=403)


@app.exception_handler(HTTPException)
async def _http(request, exc):
    return HTMLResponse(f"<h3>{exc.status_code}</h3><p>{html.escape(str(exc.detail))}</p><p><a href='/'>Home</a></p>",
                        status_code=exc.status_code)


@app.get("/healthz", include_in_schema=False)
def healthz():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return JSONResponse({"status": "ok"})


app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(admin.router)
