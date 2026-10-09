import secrets as random_secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import secrets
from .database import session, User

bearer = HTTPBearer(auto_error=False)
attempts = defaultdict(deque)
tickets = {}
limits = defaultdict(deque)


def rate_limit(key, maximum, seconds=60, registry=None):
    registry = limits if registry is None else registry
    history = registry[key]
    current = time.monotonic()
    while history and history[0] < current - seconds:
        history.popleft()
    if len(history) >= maximum:
        raise HTTPException(429, 'Limite de tentativas. Aguarde antes de tentar novamente.')
    history.append(current)


def login(username, password, address):
    rate_limit(address, 10, 300, attempts)
    rate_limit('user:' + username, 5, 300, attempts)
    with session() as db:
        user = db.get(User, username)
        hashed = user.password_hash.encode() if user else bcrypt.hashpw(b'invalid', bcrypt.gensalt())
        valid = len(password.encode()) <= 72 and bcrypt.checkpw(password.encode(), hashed)
        if not user or not user.active or not valid:
            raise HTTPException(401, 'Usuário ou senha inválidos.')
        token = jwt.encode({'sub': user.username, 'exp': datetime.now(timezone.utc) + timedelta(hours=4), 'iat': datetime.now(timezone.utc)}, secrets()['jwt_secret'], algorithm='HS256')
        return {'token': token, 'user': {'username': user.username, 'role': user.role}}


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, 'Faça login para continuar.')
    try:
        payload = jwt.decode(credentials.credentials, secrets()['jwt_secret'], algorithms=['HS256'])
        with session() as db:
            user = db.get(User, payload['sub'])
            if not user or not user.active:
                raise HTTPException(401, 'Sessão inválida.')
            return {'username': user.username, 'role': user.role}
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(401, 'Sessão expirada ou inválida.')


def require(*roles):
    def dependency(user=Depends(current_user)):
        if user['role'] not in roles:
            raise HTTPException(403, 'Seu papel não permite esta operação.')
        return user
    return dependency


def issue_ticket(user):
    current = time.monotonic()
    for token, (_, expires) in list(tickets.items()):
        if expires < current:
            del tickets[token]
    token = random_secrets.token_urlsafe(32)
    tickets[token] = (user, current + 20)
    return token


def consume_ticket(token):
    user, expires = tickets.pop(token, (None, 0))
    return user if expires > time.monotonic() else None
