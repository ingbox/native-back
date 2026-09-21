from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.deps import find_user_rooms, get_owned_room
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
        rooms = await find_user_rooms(db, user.id)
        if not rooms:
            await websocket.close(code=4404)
            return
        room_ids = [room.id for room in rooms]

    await websocket.accept()
    for room_id in room_ids:
        manager.join(room_id, user.id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")
            payload_data = data.get("payload") or {}

            if event_type == "message.send":
                digits = str(payload_data.get("digits") or "").strip()
                raw_room_id = payload_data.get("room_id")
                if not digits or len(digits) > 64 or not raw_room_id:
                    await websocket.send_json({"type": "error", "payload": {"detail": "메시지가 올바르지 않아요"}})
                    continue

                async with SessionLocal() as db:
                    try:
                        room = await get_owned_room(db, user.id, UUID(str(raw_room_id)))
                    except Exception:
                        await websocket.send_json({"type": "error", "payload": {"detail": "채팅방을 찾을 수 없어요"}})
                        continue

                    message = Message(room_id=room.id, sender_id=user.id, digits=digits)
                    db.add(message)
                    await db.commit()
                    await db.refresh(message)
                    payload = {
                        "type": "message.new",
                        "payload": {
                            "id": str(message.id),
                            "room_id": str(room.id),
                            "digits": message.digits,
                            "sender_id": str(message.sender_id),
                            "created_at": message.created_at.isoformat(),
                        },
                    }

                await manager.broadcast(room.id, payload)

            elif event_type == "typing":
                raw_room_id = payload_data.get("room_id")
                if not raw_room_id:
                    continue
                room_id = UUID(str(raw_room_id))
                if room_id not in room_ids:
                    continue
                await manager.broadcast(
                    room_id,
                    {"type": "typing", "payload": {"user_id": str(user.id), "room_id": str(room_id)}},
                    exclude=user.id,
                )
    except WebSocketDisconnect:
        manager.leave_all(user.id)
    except Exception:
        manager.leave_all(user.id)
