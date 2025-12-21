"""FastAPI backend for Cribbage game.

This API converts the synchronous cribbage game into a stateful web service.
The game maintains state between API calls and waits for player input via POST requests.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Set
from enum import Enum
import uuid
import random


from cribbage.connection_manager import ConnectionManager
from cribbage.game_state import GameState
from cribbage.models import ActionType, GameStateResponse, PlayerAction
from cribbage.playingcards import Card, Deck
from cribbage import scoring


app = FastAPI(title="Cribbage API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== In-memory game storage =====
games: Dict[str, GameState] = {}
manager = ConnectionManager()


# ===== API Endpoints =====
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Cribbage API is running",
        "active_games": len(games)
    }


@app.post("/game/new", response_model=GameStateResponse)
async def create_game():
    """Create a new game and start the first round."""
    game_id = str(uuid.uuid4())
    game = GameState(game_id)
    games[game_id] = game
    
    game.start_round()
    state = game.get_state_response()
    await manager.broadcast_state(game_id, state)
    return state


@app.get("/game/{game_id}", response_model=GameStateResponse)
async def get_game_state(game_id: str):
    """Get the current state of a game."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return games[game_id].get_state_response()


@app.websocket("/ws/{game_id}")
async def websocket_game_state(websocket: WebSocket, game_id: str):
    """WebSocket endpoint to stream game state updates in real time."""
    if game_id not in games:
        await websocket.close(code=1008)
        return
    await manager.connect(game_id, websocket)
    try:
        # Send initial state
        await manager.send_state(websocket, games[game_id].get_state_response())
        # Keep the connection alive; incoming messages are ignored (client pushes via REST)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)


@app.post("/game/{game_id}/action", response_model=GameStateResponse)
async def submit_action(game_id: str, action: PlayerAction):
    """Submit a player action (crib cards or card to play)."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    
    try:
        if game.waiting_for_action == ActionType.SELECT_CRIB_CARDS:
            game.submit_crib_cards(action.card_indices)
        elif game.waiting_for_action == ActionType.SELECT_CARD_TO_PLAY:
            game.submit_play_card(action.card_indices)
        else:
            raise HTTPException(status_code=400, detail="No action expected at this time")
        state = game.get_state_response()
        await manager.broadcast_state(game_id, state)
        return state
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/game/{game_id}")
async def delete_game(game_id: str):
    """Delete a game session."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    del games[game_id]
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
