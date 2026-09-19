from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.deps import find_user_room
from app.models.message import Message
from app.models.user import User
from app.security import decode_token
from app.services.ws_manager import manager

router = APIRouter(tags=["ws"])


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)) -> None:
    try:
        user_id = decode_token(token, "access")
    except Exception:
        await websocket.close(code=4401)
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            await websocket.close(code=4401)
            return
        room = await find_user_room(db, user.id)
        if room is None:
            await websocket.close(code=4404)
            return
        room_id = room.id

    await manager.connect(room_id, user.id, websocket)
    await manager.broadcast(
        room_id,
        {"type": "partner.online", "payload": {"user_id": str(user.id)}},
        exclude=user.id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "message.send":
                digits = str((data.get("payload") or {}).get("digits") or "").strip()
                if not digits or len(digits) > 64:
                    await websocket.send_json({"type": "error", "payload": {"detail": "메시지가 올바르지 않아요"}})
                    continue

                async with SessionLocal() as db:
                    message = Message(room_id=room_id, sender_id=user.id, digits=digits)
                    db.add(message)
                    await db.commit()
                    await db.refresh(message)
                    payload = {
                        "type": "message.new",
                        "payload": {
                            "id": str(message.id),
                            "digits": message.digits,
                            "sender_id": str(message.sender_id),
                            "created_at": message.created_at.isoformat(),
                        },
                    }

                await manager.broadcast(room_id, payload)

            elif event_type == "typing":
                await manager.broadcast(
                    room_id,
                    {"type": "typing", "payload": {"user_id": str(user.id)}},
                    exclude=user.id,
                )
    except WebSocketDisconnect:
        manager.disconnect(room_id, user.id)
        await manager.broadcast(
            room_id,
            {"type": "partner.offline", "payload": {"user_id": str(user.id)}},
        )
    except Exception:
        manager.disconnect(room_id, user.id)
