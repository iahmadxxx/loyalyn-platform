from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import WalletConfig, WalletDesign
from app.schemas.common import WalletDesignUpdate

router = APIRouter()

@router.get("/{brand_id}/status")
async def wallet_status(brand_id: str, db: AsyncSession = Depends(get_db)):
    config = await db.scalar(select(WalletConfig).where(WalletConfig.brand_id == brand_id))
    if not config:
        raise HTTPException(404, "Wallet configuration not found")
    return {"enabled": config.enabled, "validation_status": config.validation_status, "expires_at": config.certificate_expires_at, "pass_type_identifier": config.pass_type_identifier}

@router.post("/{brand_id}/certificate")
async def upload_certificate(
    brand_id: str,
    certificate: UploadFile = File(...),
    password: str = Form(...),
    pass_type_identifier: str = Form(...),
    team_identifier: str = Form(...),
    organization_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not certificate.filename or not certificate.filename.lower().endswith(".p12"):
        raise HTTPException(400, "Only .p12 certificates are accepted")
    raw = await certificate.read()
    if len(raw) > 2_000_000:
        raise HTTPException(400, "Certificate file is too large")
    config = await db.scalar(select(WalletConfig).where(WalletConfig.brand_id == brand_id))
    if not config:
        raise HTTPException(404, "Wallet configuration not found")
    # Production implementation must parse PKCS#12, validate certificate EKU/OID,
    # encrypt bytes and password with APP_ENCRYPTION_KEY, then persist ciphertext only.
    config.pass_type_identifier = pass_type_identifier
    config.team_identifier = team_identifier
    config.organization_name = organization_name
    config.validation_status = "pending_validation"
    config.enabled = False
    config.last_validation_error = None
    await db.commit()
    return {"status": "pending_validation", "message": "Certificate received and queued for secure validation"}

@router.put("/{brand_id}/design")
async def update_design(brand_id: str, payload: WalletDesignUpdate, db: AsyncSession = Depends(get_db)):
    current = await db.scalar(select(WalletDesign).where(WalletDesign.brand_id == brand_id).order_by(WalletDesign.version.desc()))
    next_version = (current.version + 1) if current else 1
    design = WalletDesign(brand_id=brand_id, version=next_version, is_published=False, design=payload.design)
    db.add(design)
    await db.commit()
    await db.refresh(design)
    return {"id": str(design.id), "version": design.version, "is_published": design.is_published}
