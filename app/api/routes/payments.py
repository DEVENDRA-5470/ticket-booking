from fastapi import APIRouter
router = APIRouter()
@router.post("/{booking_id}")
def create_payment(booking_id: int):
    return {"message": "Payment flow placeholder", "booking_id": booking_id}
