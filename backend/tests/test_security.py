from app.core.security import decrypt_secret, encrypt_secret


def test_secret_round_trip():
    protected = encrypt_secret("wallet-password")
    assert protected != "wallet-password"
    assert decrypt_secret(protected) == "wallet-password"
