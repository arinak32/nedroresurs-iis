from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import Token, UserOut
from ..security import create_token, current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["Вход"])


@router.post("/login", response_model=Token, summary="Вход по логину и паролю")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.login == form.username.strip().lower()))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")
    return Token(access_token=create_token(user))


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: User = Depends(current_user)):
    return user
