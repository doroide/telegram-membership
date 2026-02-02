from fastapi import APIRouter, Request
from backend.app.db.session import async_session
from backend.app.services.membership_service import MembershipService
from backend.app.db.models import Membership

router = APIRouter()


@router.post("/renewal_webhook")
async def renewal_webhook(request: Request):

    data = await request.json()

    notes = data.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {})

    telegram_id = int(notes.get("telegram_id"))
    plan_id = notes.get("plan_id")

    # format: renew_membershipId_plan
    if not plan_id.startswith("renew_"):
        return {"ok": True}

    _, membership_id, plan = plan_id.split("_")
    membership_id = int(membership_id)

    async with async_session() as session:

        membership = await session.get(Membership, membership_id)

        await MembershipService.extend_membership(
            session,
            membership,
            plan,
            0
        )

    return {"ok": True}
