from fastapi import APIRouter
router = APIRouter()
@router.get("/")
def list_events():
    return {"module": "events", "items": []}
