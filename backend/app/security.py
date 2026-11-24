"""Аутентификация (JWT) и проверка прав по ролям (глава 2, раздел 2.2.4)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Role, User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "role": user.role.value, "iat": now, "exp": now + timedelta(hours=settings.jwt_hours)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется вход в систему",
                                 headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require(*roles: Role):
    """Зависимость FastAPI: пропускает только пользователей перечисленных ролей."""
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав для этого действия")
        return user
    return checker


# группы ролей по таблице 2.1
OFFICE = (Role.director, Role.manager, Role.accountant, Role.lawyer, Role.mechanic, Role.admin)
ORDERS_READ = (Role.director, Role.manager, Role.accountant, Role.lawyer, Role.admin)
ORDERS_EDIT = (Role.manager,)
STOCK_READ = (Role.director, Role.manager, Role.accountant, Role.admin)
STOCK_EDIT = (Role.manager,)
