from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Optional
import json
from app.auth import verify_password, create_access_token, get_current_user
from app.database import get_db_cursor
from app.schemas import Token, UserProfile, LoginRequest

router = APIRouter(prefix="/api/admin/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login(request: Request, body: Optional[LoginRequest] = None):
    email = None
    password = None

    # Check Content-Type to support both application/json and form-data/x-www-form-urlencoded
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            json_body = await request.json()
            email = json_body.get("email") or json_body.get("username")
            password = json_body.get("password")
        except Exception:
            pass
    elif "form" in content_type:
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
    
    if not email and body:
        email = body.email
        password = body.password

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email/username and password are required",
        )

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, email, password_hash, full_name, organization, role, distributor_id, is_active, created_at
            FROM dashboard_users
            WHERE LOWER(email) = LOWER(%s);
        """, (email.strip(),))
        user = cur.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive. Contact administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_profile = UserProfile(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        organization=user["organization"],
        role=user["role"],
        distributor_id=user["distributor_id"],
        is_active=user["is_active"],
        created_at=user["created_at"],
    )

    access_token = create_access_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "distributor_id": user["distributor_id"],
        "full_name": user["full_name"],
    })

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_profile,
    )

@router.get("/me", response_model=UserProfile)
def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user
