from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import security, services
from ..db import get_db
from ..deps import client_ip, csrf_protect, flash, render, user_any

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    if request.session.get("uid"):
        return RedirectResponse("/", 303)
    return render(request, "login.html")


@router.post("/login", dependencies=[Depends(csrf_protect)])
def login(request: Request, username: str = Form(""), password: str = Form(""), db: Session = Depends(get_db)):
    ip = client_ip(request)
    if not security.login_limiter.allow(ip or "unknown"):
        return render(request, "login.html", error="Too many attempts. Wait a few minutes and try again.")
    try:
        u = services.authenticate(db, username, password, ip)
    except services.Invalid as e:
        return render(request, "login.html", error=e.errors[0], username=username)
    request.session.clear()
    request.session.update(uid=u.id, ver=u.session_version, csrf=security.new_csrf())
    return RedirectResponse("/account/password" if u.must_change_password else "/", 303)


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 303)


@router.get("/account/password")
def password_page(request: Request, user=Depends(user_any)):
    return render(request, "password.html", user)


@router.post("/account/password", dependencies=[Depends(csrf_protect)])
def password_submit(request: Request, old: str = Form(""), new: str = Form(""), new2: str = Form(""),
                    user=Depends(user_any), db: Session = Depends(get_db)):
    if new != new2:
        return render(request, "password.html", user, errors=["The new passwords do not match."])
    try:
        services.change_password(db, user, old, new, client_ip(request))
    except services.Invalid as e:
        return render(request, "password.html", user, errors=e.errors)
    request.session["ver"] = user.session_version   # keep this browser signed in
    flash(request, "Password changed.")
    return RedirectResponse("/", 303)
