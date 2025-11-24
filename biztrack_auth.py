from __future__ import annotations

import getpass
import secrets
from typing import Optional, Tuple

from biztrack_db import execute_query

# Hashing parameters should match those in main module
HASH_NAME = "sha256"
ITERATIONS = 400_000
SALT_BYTES = 16
KEY_LEN = 32

import hashlib

def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt, ITERATIONS, dklen=KEY_LEN)
    return salt.hex(), key.hex()

def verify_password(password: str, salt_hex: str, key_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(key_hex)
    key = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt, ITERATIONS, dklen=len(expected))
    return secrets.compare_digest(key, expected)


def admin_exists() -> bool:
    r = execute_query("SELECT COUNT(*) FROM Admins;", fetchone=True)
    return bool(r and r[0] > 0)


def set_admin_password_interactive() -> None:
    print("=== Set Admin Password ===")
    username = input("Admin username (default 'admin'): ").strip() or "admin"
    while True:
        pw = getpass.getpass("Enter new password: ")
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print("Passwords do not match — try again.")
            continue
        if len(pw) < 6:
            print("Password too short — minimum 6 characters.")
            continue
        salt_hex, key_hex = hash_password(pw)
        try:
            execute_query("""
                INSERT INTO Admins (username, salt, passhash)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET salt=excluded.salt, passhash=excluded.passhash;
            """, (username, salt_hex, key_hex), commit=True)
            print("Admin password set.")
            break
        except Exception as exc:
            print(f"[Admin Save Error] {exc}")
            break


def login() -> bool:
    import getpass as _gp
    print("\n=== Admin Login ===")
    username = input("Admin username: ").strip()
    pw = _gp.getpass("Password: ")
    try:
        row = execute_query("SELECT salt, passhash FROM Admins WHERE username=?;", (username,), fetchone=True)
        if not row:
            print("Unknown admin username.")
            return False
        salt_hex, key_hex = row
        if verify_password(pw, salt_hex, key_hex):
            print("\n--- Welcome back Admin! ---")
            return True
        print("\nWrong Credentials!")
        return False
    except Exception as exc:
        print(f"[Login Error] {exc}")
        return False


def reset_admin_password_cli():
    print("=== Reset Admin Password (requires current password) ===")
    username = input("Admin username: ").strip()
    if not username:
        print("Username required.")
        return
    current = getpass.getpass("Current password: ")
    row = execute_query("SELECT salt, passhash FROM Admins WHERE username = ?;", (username,), fetchone=True)
    if not row:
        print("Admin user not found.")
        return
    salt, ph = row
    if not verify_password(current, salt, ph):
        print("Current password incorrect.")
        return
    while True:
        newpw = getpass.getpass("New password: ")
        newpw2 = getpass.getpass("Confirm new password: ")
        if newpw != newpw2:
            print("Passwords do not match.")
            continue
        if len(newpw) < 6:
            print("Password too short; min 6 chars.")
            continue
        s_hex, k_hex = hash_password(newpw)
        execute_query("UPDATE Admins SET salt=?, passhash=? WHERE username=?;", (s_hex, k_hex, username), commit=True)
        print("Password updated.")
        break
