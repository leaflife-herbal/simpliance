from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import hr, services
from ..db import get_db
from ..deps import csrf_protect, current_user, render

router = APIRouter()


@router.get("/")
def home(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    cos = services.companies_for(db, user)
    cid = request.session.get("company_id")
    if cid not in [c.id for c in cos]:
        cid = cos[0].id if cos else None
        request.session["company_id"] = cid
    current = next((c for c in cos if c.id == cid), None)
    lic_due, sub_due = services.expiring(db) if user.is_super else ([], [])
    return render(request, "home.html", user, companies=cos, current=current,
                  read_only=services.read_only_reason(db, user),
                  dash=hr.dashboard(db, current.id) if current else None, lic_due=lic_due, sub_due=sub_due)


@router.post("/company/select", dependencies=[Depends(csrf_protect)])
def select_company(request: Request, company_id: int = Form(...), user=Depends(current_user),
                   db: Session = Depends(get_db)):
    if company_id in [c.id for c in services.companies_for(db, user)]:   # tenant boundary check
        request.session["company_id"] = company_id
    return RedirectResponse("/", 303)
