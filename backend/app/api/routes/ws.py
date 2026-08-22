from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket import ws_manager

router = APIRouter()

@router.websocket("/ws/execution")
async def execution_websocket(websocket: WebSocket):
    """
    Real-time WebSocket connection endpoint for receiving live MES execution updates,
    state changes, resource occupancy shifts, and execution logs.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive receive loop
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
