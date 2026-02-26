import os

import socketio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.lifecycle import register_lifecycle_events
from api.routes import register_routes
from realtime.chat_events import register_chat_events

load_dotenv()

PORT = int(os.getenv("PORT", "8001"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

if FRONTEND_ORIGIN.strip() == "*":
    cors_allowed_origins: str | list[str] = "*"
else:
    cors_allowed_origins = [origin.strip() for origin in FRONTEND_ORIGIN.split(",") if origin.strip()]

fastapi_app = FastAPI(title="AI Runtime Socket Server")
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_allowed_origins == "*" else cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(fastapi_app)
register_lifecycle_events(fastapi_app)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_allowed_origins)
register_chat_events(sio)

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)
