from dataclasses import dataclass

import chess

from .engine import EngineResult


@dataclass(frozen=True)
class Evaluation:
    kind: str
    value: int
    display: str


def board_from_fen(fen: str) -> chess.Board:
    return chess.Board(fen)


def status(board: chess.Board) -> dict[str, object]:
    if board.is_checkmate():
        return {"state": "checkmate", "winner": "black" if board.turn else "white", "inCheck": True}
    if board.is_stalemate():
        return {"state": "stalemate", "winner": None, "inCheck": False}
    if board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        return {"state": "draw", "winner": None, "inCheck": board.is_check()}
    if board.is_check():
        return {"state": "check", "winner": None, "inCheck": True}
    return {"state": "playing", "winner": None, "inCheck": False}


def human_score(result: EngineResult, human_color: str) -> tuple[int, int | None]:
    white_score = result.score.white()
    mate = white_score.mate()
    if mate is not None:
        signed_mate = mate if human_color == "white" else -mate
        return (100000 if signed_mate > 0 else -100000), signed_mate
    value = white_score.score(mate_score=100000) or 0
    return (value if human_color == "white" else -value), None


def evaluation(result: EngineResult, human_color: str) -> Evaluation:
    value, mate = human_score(result, human_color)
    if mate is not None:
        display = "Mate" if abs(mate) == 1 else f"M{abs(mate)}"
        return Evaluation("mate", value, f"{'+' if mate > 0 else '-'}{display}")
    return Evaluation("centipawn", value, f"{value / 100:+.2f}")


def delta(before: Evaluation, after: Evaluation) -> Evaluation:
    if before.kind == "centipawn" and after.kind == "centipawn":
        value = after.value - before.value
        return Evaluation("centipawn", value, f"{value / 100:+.2f}")
    if before.kind == "mate" and after.kind == "mate" and (before.value > 0) == (after.value > 0):
        return Evaluation("mate", 0, "~0.00")
    value = after.value - before.value
    return Evaluation("mate", value, "+Mate" if value > 0 else "-Mate")


def evaluation_dict(item: Evaluation) -> dict[str, object]:
    return {"type": item.kind, "value": item.value, "display": item.display}


def game_state(board: chess.Board) -> dict[str, object]:
    return {"fen": board.fen(), "status": status(board)}
