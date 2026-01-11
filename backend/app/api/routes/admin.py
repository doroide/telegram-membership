from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import User
import csv
import io

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


@router.get("/dashboard")
async def dashboard(request: Request):
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "users": users
    })


@router.get("/export_csv")
async def export_csv():
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["telegram_id", "username", "plan", "expiry_date", "status"])

    for u in users:
        writer.writerow([
            u.telegram_id,
            u.username,
            u.plan,
            u.expiry_date.strftime("%Y-%m-%d") if u.expiry_date else "",
            "ACTIVE" if u.is_active else "EXPIRED"
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"}
    )
