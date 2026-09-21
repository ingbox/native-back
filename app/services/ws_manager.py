from __future__ import annotations

from collections import defaultdict
from typing import Optional
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[UUID, dict[UUID, WebSocket]] = defaultdict(dict)

    async def connect(self, room_id: UUID, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self.join(room_id, user_id, websocket)

    def join(self, room_id: UUID, user_id: UUID, websocket: WebSocket) -> None:
        self.rooms[room_id][user_id] = websocket

    def leave_all(self, user_id: UUID) -> list[UUID]:
        left: list[UUID] = []
        for room_id in list(self.rooms.keys()):
            if user_id in self.rooms.get(room_id, {}):
                self.disconnect(room_id, user_id)
                left.append(room_id)
        return left

    def disconnect(self, room_id: UUID, user_id: UUID) -> None:
        connections = self.rooms.get(room_id)
        if not connections:
            return
        connections.pop(user_id, None)
        if not connections:
            self.rooms.pop(room_id, None)

    async def send_to_user(self, room_id: UUID, user_id: UUID, payload: dict) -> None:
        websocket = self.rooms.get(room_id, {}).get(user_id)
        if websocket is None:
            return
        try:
            await websocket.send_json(payload)
        except Exception:
            self.disconnect(room_id, user_id)

    async def broadcast(self, room_id: UUID, payload: dict, exclude: Optional[UUID] = None) -> None:
        for user_id, websocket in list(self.rooms.get(room_id, {}).items()):
            if exclude is not None and user_id == exclude:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(room_id, user_id)


manager = ConnectionManager()
