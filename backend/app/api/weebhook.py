from fastapi import APIRouter

router = APIRouter()

@router.post("/razorpay")
async def razorpay_webhook():
    return {"status": "webhook reached"}
