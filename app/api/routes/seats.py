from fastapi import APIRouter
router = APIRouter()
@router.get("/event/{event_id}")
def list_seats(event_id: int):
    return {"module": "seats", "event_id": event_id, "items": []}
