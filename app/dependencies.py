from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


ROLE_MENUS = {
    "admin": ["home", "dashboard", "monitor", "analysis", "alarms", "devices", "settings", "access", "visitors", "sensors", "map", "users"],
    "security": ["home", "dashboard", "monitor", "analysis", "alarms", "devices", "settings", "access", "visitors", "sensors", "map"],
    "teacher": ["home", "dashboard", "analysis", "alarms", "visitors", "map"],
    "viewer": ["home", "dashboard", "map"],
}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        request.session.clear()
        return None
    user = db.get(User, user_id_int)
    if not user or not user.is_active:
        request.session.clear()
        return None
    return user


def require_api_roles(*roles: str) -> Callable:
    def dependency(user: User | None = Depends(get_current_user)) -> User:
        if not user:
            raise HTTPException(status_code=401, detail="Not logged in")
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return dependency


def ensure_page_user(request: Request, user: User | None):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return None


def user_context(user: User | None) -> dict:
    menus = ROLE_MENUS.get(user.role, []) if user else []
    return {"current_user": user, "menus": menus}
