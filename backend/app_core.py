import os
import random
import string
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# --------------------------------------------------------------------------
# Configuration (set these as environment variables on Render/Railway)
# --------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-secret")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@example.com")
SENDER_NAME = os.environ.get("SENDER_NAME", "AL-HUDA")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./alhuda.db")
# Neon/Supabase/Heroku-style URLs sometimes use the old "postgres://" scheme;
# SQLAlchemy 2.x requires "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
CODE_EXPIRY_MINUTES = 15

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    city = Column(String, default="")
    country = Column(String, default="")
    is_verified = Column(Boolean, default=False)
    verify_code = Column(String, nullable=True)
    verify_code_expires = Column(DateTime, nullable=True)
    reset_code = Column(String, nullable=True)
    reset_code_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)

# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(title="AL-HUDA Auth API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    city: str = ""
    country: str = ""


class VerifyIn(BaseModel):
    email: EmailStr
    code: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    email: EmailStr
    code: str
    new_password: str


def _gen_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(email: str) -> str:
    payload = {"email": email, "iat": int(time.time())}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _send_email(to_email: str, subject: str, html_body: str):
    """Sends an email via Brevo's transactional email API."""
    if not BREVO_API_KEY:
        # No API key configured yet — skip sending so local/dev testing
        # doesn't crash. Codes will still be visible in server logs.
        print(f"[DEV] Would send to {to_email}: {subject}\n{html_body}")
        return
    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
        },
        timeout=15,
    )
    if resp.status_code >= 300:
        print(f"[WARN] Brevo send failed ({resp.status_code}): {resp.text}")


def _now():
    return datetime.now(timezone.utc)


@app.post("/auth/register")
def register(data: RegisterIn):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == data.email).first()
        if existing and existing.is_verified:
            raise HTTPException(400, "An account with this email already exists.")

        code = _gen_code()
        expires = _now() + timedelta(minutes=CODE_EXPIRY_MINUTES)

        if existing:
            existing.password_hash = _hash_password(data.password)
            existing.city = data.city
            existing.country = data.country
            existing.verify_code = code
            existing.verify_code_expires = expires
        else:
            existing = User(
                email=data.email,
                password_hash=_hash_password(data.password),
                city=data.city,
                country=data.country,
                verify_code=code,
                verify_code_expires=expires,
            )
            db.add(existing)
        db.commit()

        _send_email(
            data.email,
            "Verify your AL-HUDA account",
            f"<p>Assalamu Alaikum,</p><p>Your AL-HUDA verification code is:</p>"
            f"<h2>{code}</h2><p>This code expires in {CODE_EXPIRY_MINUTES} minutes.</p>",
        )
        return {"message": "Verification code sent."}
    finally:
        db.close()


@app.post("/auth/verify")
def verify(data: VerifyIn):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == data.email).first()
        if not user or not user.verify_code:
            raise HTTPException(400, "No pending verification for this email.")
        if user.verify_code_expires and user.verify_code_expires < _now():
            raise HTTPException(400, "This code has expired. Please register again.")
        if user.verify_code != data.code:
            raise HTTPException(400, "Incorrect code.")
        user.is_verified = True
        user.verify_code = None
        user.verify_code_expires = None
        db.commit()
        return {"message": "Account verified."}
    finally:
        db.close()


@app.post("/auth/login")
def login(data: LoginIn):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == data.email).first()
        if not user or not _check_password(data.password, user.password_hash):
            raise HTTPException(401, "Incorrect email or password.")
        if not user.is_verified:
            raise HTTPException(403, "Please verify your email before logging in.")
        token = _make_token(user.email)
        return {"token": token, "city": user.city, "country": user.country}
    finally:
        db.close()


@app.post("/auth/forgot-password")
def forgot_password(data: ForgotIn):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == data.email).first()
        # Always respond success (don't reveal whether the email exists).
        if user:
            code = _gen_code()
            user.reset_code = code
            user.reset_code_expires = _now() + timedelta(minutes=CODE_EXPIRY_MINUTES)
            db.commit()
            _send_email(
                data.email,
                "Reset your AL-HUDA password",
                f"<p>Your AL-HUDA password reset code is:</p><h2>{code}</h2>"
                f"<p>This code expires in {CODE_EXPIRY_MINUTES} minutes. "
                f"If you didn't request this, you can ignore this email.</p>",
            )
        return {"message": "If that email exists, a reset code has been sent."}
    finally:
        db.close()


@app.post("/auth/reset-password")
def reset_password(data: ResetIn):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == data.email).first()
        if not user or not user.reset_code:
            raise HTTPException(400, "No pending reset for this email.")
        if user.reset_code_expires and user.reset_code_expires < _now():
            raise HTTPException(400, "This code has expired. Please request a new one.")
        if user.reset_code != data.code:
            raise HTTPException(400, "Incorrect code.")
        user.password_hash = _hash_password(data.new_password)
        user.reset_code = None
        user.reset_code_expires = None
        db.commit()
        return {"message": "Password reset successful."}
    finally:
        db.close()


@app.get("/")
def health():
    return {"status": "AL-HUDA backend is running"}
