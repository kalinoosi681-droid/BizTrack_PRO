from biztrack import hash_password, verify_password


def test_password_hash_and_verify():
    pw = "s3cret-pass"
    salt_hex, key_hex = hash_password(pw)
    assert isinstance(salt_hex, str) and isinstance(key_hex, str)
    assert verify_password(pw, salt_hex, key_hex) is True
    assert verify_password("badpass", salt_hex, key_hex) is False
