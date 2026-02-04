from fastapi import APIRouter, Request
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment
from backend.app.services.membership_service import MembershipService

router = APIRouter()


# =====================================================
# Razorpay Webhook
# =====================================================

@router.post("/webhook")
async def razorpay_webhook(request: Request):

    data = await request.json()

    try:
        event = data.get("event")

        # we only care about successful payments
        if event != "payment.captured":
            return {"ok": True}

        payment_entity = data["payload"]["payment"]["entity"]

        notes = payment_entity.get("notes", {})

        telegram_id = int(notes.get("telegram_id"))
        plan_id = notes.get("plan_id")

        amount = payment_entity["amount"] / 100  # paise → rupees
        razorpay_payment_id = payment_entity["id"]

        async with async_session() as session:

            # -----------------------------------
            # create/find user
            # -----------------------------------
            user = await session.get(User, telegram_id)

            if not user:
                user = User(id=telegram_id)
                session.add(user)

            # -----------------------------------
            # save payment
            # -----------------------------------
            payment = Payment(
                user_id=telegram_id,
                amount=amount,
                razorpay_payment_id=razorpay_payment_id,
                status="captured"
            )
            session.add(payment)

            # -----------------------------------
            # create/extend membership
            # -----------------------------------
            await MembershipService.handle_successful_payment(
                session=session,
                user_id=telegram_id,
                plan_id=plan_id,
                amount=amount
            )

            await session.commit()

        print("✅ Payment processed:", telegram_id, plan_id)

        return {"ok": True}

    except Exception as e:
        print("❌ Webhook processing error:", str(e))
        return {"ok": False}
