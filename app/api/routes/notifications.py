from fastapi import APIRouter
router = APIRouter()
@router.get("/")
def list_notifications():
    return {"module": "notifications", "items": []}
