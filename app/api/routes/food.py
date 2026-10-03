from fastapi import APIRouter
router = APIRouter()
@router.get("/items")
def list_food():
    return {"module": "food", "items": []}
