"""Deliberately fake authentication.

Do not improve this. It is out of scope and exists only to simulate a multi-user server.
"""

from fastapi import Cookie, Depends, HTTPException

from .models import EmailPointer, Member
from .store import Store, get_store

COOKIE_NAME = "peak_session"

MEMBERS = "user"
EMAIL_INDEX = "email"


def find_by_email(store: Store, email: str) -> Member | None:
    pointer = store.get(EMAIL_INDEX, email.strip().lower(), EmailPointer)
    if pointer is None:
        return None
    return store.get(MEMBERS, pointer.user_id, Member)


def current_user(
    peak_session: str | None = Cookie(default=None),
    store: Store = Depends(get_store),
) -> Member:
    if not peak_session:
        raise HTTPException(status_code=401, detail="Not signed in")

    member = store.get(MEMBERS, peak_session, Member)
    if member is None:
        raise HTTPException(status_code=401, detail="Not signed in")

    return member
