"""Serviços de autenticação: hash, login, sessão, CSRF (Spec E2)."""

from __future__ import annotations

import hmac
import re
import secrets
from datetime import UTC, timedelta
from datetime import datetime as _datetime
from hashlib import sha256
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.exc import IntegrityError

from backuplc.auth.models import User, UserSession
from backuplc.core.db import Database, utcnow
from backuplc.core.errors import DuplicateError


def _utc(dt: _datetime) -> _datetime:
    """Garante que um datetime é timezone-aware UTC (SQLite pode retornar naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


_ph = PasswordHasher()

SESSION_TTL = timedelta(hours=8)
LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)

# Comprimento mínimo e regras de complexidade (E2-01, F-10).
_PASSWORD_MIN_LEN = 12
_RE_UPPER = re.compile(r"[A-Z]")
_RE_LOWER = re.compile(r"[a-z]")
_RE_DIGIT = re.compile(r"[0-9]")

AuthResult = Literal["ok", "invalid_credentials", "account_locked"]


# ---------------------------------------------------------------------------
# Senha
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def validate_password_policy(password: str) -> None:
    """Levanta ValueError se a senha não atende à política mínima."""
    if (
        len(password) < _PASSWORD_MIN_LEN
        or not _RE_UPPER.search(password)
        or not _RE_LOWER.search(password)
        or not _RE_DIGIT.search(password)
    ):
        raise ValueError("Senha não atende à política")


# ---------------------------------------------------------------------------
# Sessão
# ---------------------------------------------------------------------------


def create_session(db: Database, user_id: str) -> str:
    """Cria uma sessão e retorna o session_id."""
    session_id = secrets.token_hex(32)
    now = utcnow()
    session = UserSession(
        id=session_id,
        user_id=user_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_TTL,
    )
    with db.session() as s:
        s.add(session)
    return session_id


def get_session_user(db: Database, session_id: str) -> User | None:
    """Retorna o usuário da sessão se ela existir e não estiver expirada."""
    with db.session() as s:
        sess = s.get(UserSession, session_id)
        if sess is None:
            return None
        if utcnow() >= _utc(sess.expires_at):
            s.delete(sess)
            return None
        user = s.get(User, sess.user_id)
        if user is None or not user.is_active:
            s.delete(sess)
            return None
        return user


def touch_session(db: Database, session_id: str) -> None:
    """Atualiza last_seen_at e extends expires_at."""
    now = utcnow()
    with db.session() as s:
        sess = s.get(UserSession, session_id)
        if sess is not None:
            sess.last_seen_at = now
            sess.expires_at = now + SESSION_TTL


def delete_session(db: Database, session_id: str) -> None:
    with db.session() as s:
        sess = s.get(UserSession, session_id)
        if sess is not None:
            s.delete(sess)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def login(db: Database, username: str, password: str) -> tuple[AuthResult, User | None]:
    """
    Tenta autenticar. Retorna (resultado, usuário).
    Nunca distingue usuário inválido de senha errada na mensagem (E2-04).
    """
    with db.session() as s:
        user = s.query(User).filter_by(username=username).first()
        if user is None:
            return "invalid_credentials", None

        now = utcnow()
        if user.locked_until is not None and now < _utc(user.locked_until):
            return "account_locked", None

        if not verify_password(user.password_hash, password):
            user.failed_attempts += 1
            if user.failed_attempts >= LOCKOUT_THRESHOLD:
                user.locked_until = now + LOCKOUT_DURATION
            return "invalid_credentials", None

        # Sucesso: zera contador
        user.failed_attempts = 0
        user.locked_until = None
        return "ok", user


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------


def make_csrf_token(session_id: str, session_secret: str) -> str:
    """HMAC-SHA256(session_secret, session_id) em hex."""
    return hmac.new(session_secret.encode(), session_id.encode(), sha256).hexdigest()


def verify_csrf_token(token: str, session_id: str, session_secret: str) -> bool:
    expected = make_csrf_token(session_id, session_secret)
    return hmac.compare_digest(expected, token)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def safe_next(value: str | None) -> str:
    """Valida parâmetro ?next= para evitar open redirect."""
    if not value or not value.startswith("/") or value.startswith("//") or "://" in value:
        return "/"
    return value


VALID_ROLES: frozenset[str] = frozenset({"admin", "operator", "reader"})


def create_user(db: Database, username: str, password: str, role: str) -> User:
    if role not in VALID_ROLES:
        raise ValueError(f"Perfil inválido: {role}")
    validate_password_policy(password)
    user = User(username=username, password_hash=hash_password(password), role=role)
    try:
        with db.session() as s:
            s.add(user)
    except IntegrityError:
        raise DuplicateError(f"Usuário '{username}' já existe") from None
    return user


def list_users(db: Database) -> list[User]:
    with db.session() as s:
        return s.query(User).order_by(User.username).all()


def get_user(db: Database, user_id: str) -> User | None:
    with db.session() as s:
        return s.get(User, user_id)


def update_user(
    db: Database,
    user_id: str,
    username: str,
    role: str,
    is_active: bool,
) -> User:
    if role not in VALID_ROLES:
        raise ValueError(f"Perfil inválido: {role}")
    with db.session() as s:
        user = s.get(User, user_id)
        if user is None:
            raise ValueError("Usuário não encontrado")
        user.username = username
        user.role = role
        user.is_active = is_active
        return User(
            id=user.id,
            username=user.username,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
        )


def change_password(db: Database, user_id: str, new_password: str) -> None:
    validate_password_policy(new_password)
    with db.session() as s:
        user = s.get(User, user_id)
        if user is None:
            raise ValueError("Usuário não encontrado")
        user.password_hash = hash_password(new_password)
        user.failed_attempts = 0
        user.locked_until = None


def delete_user(db: Database, user_id: str) -> None:
    with db.session() as s:
        user = s.get(User, user_id)
        if user is not None:
            s.delete(user)
