from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import json
import uuid
from typing import Dict, List

app = FastAPI(title="Video Chat Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.rooms: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Client connected: {client_id}")
    
    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        for room_id, clients in self.rooms.items():
            if client_id in clients:
                clients.remove(client_id)
        print(f"Client disconnected: {client_id}")
    
    async def send_to_client(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
    
    async def broadcast_to_room(self, message: dict, room_id: str, exclude_client: str = None):
        if room_id in self.rooms:
            for client_id in self.rooms[room_id]:
                if client_id != exclude_client and client_id in self.active_connections:
                    await self.active_connections[client_id].send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "join":
                room_id = data["room"]
                if room_id not in manager.rooms:
                    manager.rooms[room_id] = []
                manager.rooms[room_id].append(client_id)
                
                # Уведомляем других в комнате
                await manager.broadcast_to_room({
                    "type": "user_joined",
                    "client_id": client_id,
                    "username": data.get("username", "Anonymous")
                }, room_id, exclude_client=client_id)
                
                # Отправляем список участников новому клиенту
                await manager.send_to_client({
                    "type": "room_info",
                    "room_id": room_id,
                    "participants": [
                        {"id": cid, "username": "User"} 
                        for cid in manager.rooms[room_id] 
                        if cid != client_id
                    ]
                }, client_id)
            
            elif message_type == "offer":
                target = data["target"]
                await manager.send_to_client({
                    "type": "offer",
                    "sender": client_id,
                    "offer": data["offer"]
                }, target)
            
            elif message_type == "answer":
                target = data["target"]
                await manager.send_to_client({
                    "type": "answer",
                    "sender": client_id,
                    "answer": data["answer"]
                }, target)
            
            elif message_type == "ice_candidate":
                target = data["target"]
                await manager.send_to_client({
                    "type": "ice_candidate",
                    "sender": client_id,
                    "candidate": data["candidate"]
                }, target)
            
            elif message_type == "leave":
                room_id = data.get("room")
                if room_id in manager.rooms and client_id in manager.rooms[room_id]:
                    manager.rooms[room_id].remove(client_id)
                    await manager.broadcast_to_room({
                        "type": "user_left",
                        "client_id": client_id
                    }, room_id)
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)

@app.get("/")
async def root():
    return {"message": "Video Chat Server", "docs": "/docs"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "clients": len(manager.active_connections),
        "rooms": len(manager.rooms)
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
