import hashlib
import hmac
import os

from sqlalchemy.orm import Session

from app.models import User


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _, salt, digest = password_hash.split("$", 2)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return hmac.compare_digest(check, digest)


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user
