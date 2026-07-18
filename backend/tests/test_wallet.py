import json
import subprocess
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from app.models import Brand, BrandWalletDesign, Customer, PlatformWalletCredential, WalletPass
from app.services.wallet import generate_pkpass_bytes, validate_and_extract_certificate


def run(*args: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


@pytest.mark.skipif(not Path('/usr/bin/openssl').exists(), reason='openssl is required')
def test_certificate_validation_and_pkpass_generation(tmp_path: Path):
    pass_type = 'pass.com.loyalyn.tests'
    team_id = 'TEAM123456'
    signer_key = tmp_path / 'signer-source.key'
    signer_cert = tmp_path / 'signer-source.pem'
    p12 = tmp_path / 'wallet.p12'
    wwdr_key = tmp_path / 'wwdr.key'
    wwdr = tmp_path / 'wwdr.pem'
    password = 'strong-test-password'

    run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '30',
        '-keyout', str(signer_key), '-out', str(signer_cert),
        '-subj', f'/CN=Loyalyn Test/OU={team_id}/UID={pass_type}')
    run('openssl', 'pkcs12', '-export', '-out', str(p12), '-inkey', str(signer_key),
        '-in', str(signer_cert), '-passout', f'pass:{password}')
    run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '30',
        '-keyout', str(wwdr_key), '-out', str(wwdr), '-subj', '/CN=Test WWDR/O=Apple Test')

    extracted = tmp_path / 'credential'
    result = validate_and_extract_certificate(
        p12, wwdr, password, extracted,
        expected_pass_type_identifier=pass_type,
        expected_team_identifier=team_id,
    )
    assert result['expires_at'] > datetime.now(timezone.utc)
    assert (extracted / 'signer.pem').exists()
    assert (extracted / 'signer.key').exists()
    assert (extracted / 'wwdr.pem').exists()

    brand_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    credential = PlatformWalletCredential(
        id=uuid.uuid4(), filename='wallet.p12', p12_path=str(extracted / 'wallet.p12'),
        wwdr_path=str(extracted / 'wwdr.pem'), encrypted_password='unused',
        pass_type_identifier=pass_type, team_identifier=team_id,
        organization_name='Loyalyn', certificate_subject=result['certificate_subject'],
        expires_at=datetime.now(timezone.utc) + timedelta(days=30), status='active', is_active=True,
    )
    # credential_paths resolves signer files from the p12 parent.
    (extracted / 'wallet.p12').write_bytes(p12.read_bytes())
    brand = Brand(id=brand_id, name='Coffee Test', slug='coffee-test', primary_color='#111827', accent_color='#C6FF4A', currency='QAR', timezone='Asia/Qatar', locale='ar', is_active=True)
    customer = Customer(id=customer_id, brand_id=brand_id, name='Ahmed', phone='55555555', membership_code='MEMBER-001', points=120, stamps=3, available_rewards=1, tier='gold', visits=8, total_spend=250, tags=[], is_active=True)
    design = BrandWalletDesign(id=uuid.uuid4(), brand_id=brand_id, background_color='#111827', foreground_color='#FFFFFF', label_color='#C6FF4A', logo_text='COFFEE', card_title='بطاقة الولاء', barcode_format='PKBarcodeFormatQR', fields={'show_points': True, 'show_stamps': True, 'show_rewards': True, 'show_tier': True, 'show_visits': True}, draft_version=1, published_version=1, is_published=True)
    wallet_pass = WalletPass(id=uuid.uuid4(), brand_id=brand_id, customer_id=customer_id, serial_number='SERIAL-001', public_token='public-token', authentication_token='auth-token-long', pass_type_identifier=pass_type, status='active', update_tag=1)

    payload = generate_pkpass_bytes(credential=credential, brand=brand, customer=customer, design=design, wallet_pass=wallet_pass)
    assert payload.startswith(b'PK')
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = set(archive.namelist())
        assert {'pass.json', 'manifest.json', 'signature', 'icon.png', 'icon@2x.png'} <= names
        pass_json = json.loads(archive.read('pass.json'))
        assert pass_json['passTypeIdentifier'] == pass_type
        assert pass_json['teamIdentifier'] == team_id
        assert pass_json['serialNumber'] == 'SERIAL-001'
        assert pass_json['storeCard']['primaryFields'][0]['value'] == 120
        manifest = json.loads(archive.read('manifest.json'))
        assert 'pass.json' in manifest
        assert len(archive.read('signature')) > 100
