from fastapi import APIRouter
router = APIRouter()
@router.post("/")
def create_booking():
    return {"message": "Booking flow placeholder"}
