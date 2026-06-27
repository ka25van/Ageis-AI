from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    return {"status": "ok"}


@router.get("/db")
async def db_health_check():
    return {"status": "ok", "database": "connected"}