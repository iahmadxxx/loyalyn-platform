from fastapi import APIRouter
router=APIRouter()
@router.get('/health')
async def health(): return {'status':'ok','service':'loyalyn-api','version':'1.0.0'}
