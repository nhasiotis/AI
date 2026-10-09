import logging
import os
import uuid
from contextlib import asynccontextmanager

import chess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .chess_service import board_from_fen, delta, evaluation, evaluation_dict, game_state
from .engine import EngineManager
from .schemas import CandidateAnalysisRequest, ComputerMoveRequest, NewGameRequest, PlayerMoveRequest, PositionRequest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
engine_manager = EngineManager(os.getenv("STOCKFISH_PATH", "/usr/games/stockfish"))


engine_manager = EngineManager(os.getenv("STOCKFISH_PATH", "/usr/games/stockfish"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await engine_manager.start()
    try:
        yield
    finally:
        await engine_manager.stop()


app = FastAPI(title="Chess MVP API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


def invalid(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def check_turn(board: chess.Board, human_color: str) -> None:
    if board.turn != (human_color == "white"):
        raise invalid("It is not the human player's turn")


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "service": "backend", "stockfish": engine_manager.engine is not None}


@app.post("/api/game/new")
async def new_game(request: NewGameRequest) -> dict[str, object]:
    return {**game_state(chess.Board()), "humanColor": request.humanColor, "difficulty": request.difficulty}


@app.post("/api/game/legal-moves")
async def legal_moves(request: PositionRequest) -> dict[str, object]:
    try:
        board = board_from_fen(request.fen)
    except ValueError as exc:
        raise invalid("Invalid chess position") from exc
    color = request.humanColor == "white"
    legal = [move.uci() for move in board.legal_moves if board.piece_at(move.from_square) and board.piece_at(move.from_square).color == color]
    return {"fen": board.fen(), "moves": legal}


@app.post("/api/game/player-move")
async def player_move(request: PlayerMoveRequest) -> dict[str, object]:
    try:
        board = board_from_fen(request.fen)
        check_turn(board, request.humanColor)
        move = chess.Move.from_uci(request.uci)
    except (ValueError, chess.InvalidMoveError) as exc:
        raise invalid("Invalid chess move request") from exc
    if move not in board.legal_moves or board.piece_at(move.from_square) is None or board.piece_at(move.from_square).color != (request.humanColor == "white"):
        raise invalid("Move is not legal for the human player")
    san = board.san(move)
    board.push(move)
    return {**game_state(board), "move": {"uci": move.uci(), "san": san}}


@app.post("/api/game/computer-move")
async def computer_move(request: ComputerMoveRequest) -> dict[str, object]:
    try:
        board = board_from_fen(request.fen)
    except ValueError as exc:
        raise invalid("Invalid chess position") from exc
    if board.turn == (request.humanColor == "white"):
        raise invalid("It is not the computer's turn")
    move, result = await engine_manager.play(board, request.difficulty)
    san = board.san(move)
    board.push(move)
    return {**game_state(board), "move": {"uci": move.uci(), "san": san}, "evaluation": evaluation_dict(evaluation(result, request.humanColor))}


@app.post("/api/analysis/candidate-moves")
async def candidate_moves(request: CandidateAnalysisRequest) -> dict[str, object]:
    try:
        board = board_from_fen(request.fen)
        check_turn(board, request.humanColor)
        square = chess.parse_square(request.fromSquare)
    except (ValueError, chess.InvalidMoveError) as exc:
        raise invalid("Invalid analysis position or square") from exc
    piece = board.piece_at(square)
    if piece is None or piece.color != (request.humanColor == "white"):
        raise invalid("The selected square does not contain a human piece")
    selected = [move for move in board.legal_moves if move.from_square == square]
    if not selected:
        return {"fen": board.fen(), "fromSquare": request.fromSquare, "baseline": None, "moves": [], "requestId": str(uuid.uuid4())}
    baseline = evaluation(await engine_manager.analyze(board, request.depth), request.humanColor)
    moves: list[dict[str, object]] = []
    for move in selected:
        candidate = board.copy(stack=False)
        san = candidate.san(move)
        candidate.push(move)
        result = await engine_manager.analyze(candidate, request.depth)
        after = evaluation(result, request.humanColor)
        moves.append({"uci": move.uci(), "san": san, "toSquare": chess.square_name(move.to_square), "promotion": chess.piece_symbol(move.promotion) if move.promotion else None, "before": evaluation_dict(baseline), "after": evaluation_dict(after), "delta": evaluation_dict(delta(baseline, after)), "principalVariation": [item.uci() for item in result.variation] if request.includePrincipalVariation else [], "depth": result.depth})
    return {"fen": board.fen(), "fromSquare": request.fromSquare, "baseline": evaluation_dict(baseline), "moves": moves, "requestId": str(uuid.uuid4())}


@app.post("/api/analysis/position")
async def position_analysis(request: PositionRequest) -> dict[str, object]:
    try:
        board = board_from_fen(request.fen)
    except ValueError as exc:
        raise invalid("Invalid chess position") from exc
    result = await engine_manager.analyze(board, 12)
    return {"fen": board.fen(), "evaluation": evaluation_dict(evaluation(result, "white")), "depth": result.depth}
