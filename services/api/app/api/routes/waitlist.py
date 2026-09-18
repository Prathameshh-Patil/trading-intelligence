from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select

from app.api.dependencies import DB
from app.core.ratelimit import limit
from app.models import WaitlistEntry
from app.schemas import WaitlistIn
from app.services.events import ADMIN_CHANNEL, broadcaster

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def join(body: WaitlistIn, db: DB, _: None = Depends(limit("waitlist"))) -> Response:
    email = body.email.lower()
    # Joining twice is a 204 too -- the form does not need to know.
    if not db.scalar(select(WaitlistEntry.id).where(WaitlistEntry.email == email)):
        db.add(WaitlistEntry(email=email))
        db.commit()
        broadcaster.publish(ADMIN_CHANNEL, "waitlist.joined", {"email": email})
    return Response(status_code=204)
