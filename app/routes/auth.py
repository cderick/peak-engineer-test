from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..auth import COOKIE_NAME, current_user, find_by_email
from ..models import Envelope, Member, MemberPayload, MemberView, OkPayload
from ..store import Store, get_store

router = APIRouter(prefix="/api")


class LoginBody(BaseModel):
    email: str


def view(member: Member) -> MemberView:
    return MemberView(
        id=member.id,
        email=member.email,
        name=member.name,
        sex=member.sex,
        birth_date=member.birth_date,
    )


@router.post("/auth/login", response_model=Envelope[MemberPayload])
def login(body: LoginBody, response: Response, store: Store = Depends(get_store)):
    member = find_by_email(store, body.email)
    if member is None:
        raise HTTPException(status_code=401, detail="No member with that email")

    response.set_cookie(COOKIE_NAME, member.id, httponly=True, samesite="lax")
    return Envelope(data=MemberPayload(user=view(member)))


@router.post("/auth/logout", response_model=Envelope[OkPayload])
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return Envelope(data=OkPayload(ok=True))


@router.get("/me", response_model=Envelope[MemberPayload])
def me(member: Member = Depends(current_user)):
    return Envelope(data=MemberPayload(user=view(member)))
