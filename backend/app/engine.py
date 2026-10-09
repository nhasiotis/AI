import asyncio
import logging
from dataclasses import dataclass

import chess
import chess.engine

logger = logging.getLogger("chess-mvp.engine")

DIFFICULTIES = {
    "beginner": {"depth": 6, "time": 0.15},
    "easy": {"depth": 9, "time": 0.25},
    "medium": {"depth": 12, "time": 0.45},
    "hard": {"depth": 15, "time": 0.8},
    "expert": {"depth": 18, "time": 1.2},
}


@dataclass(frozen=True)
class EngineResult:
    score: chess.engine.PovScore
    variation: list[chess.Move]
    depth: int


class EngineManager:
    def __init__(self, path: str) -> None:
        self.path = path
        self.engine: chess.engine.SimpleEngine | None = None
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        async with self.lock:
            await self._restart_locked()

    async def _restart_locked(self) -> None:
        if self.engine is not None:
            try:
                await asyncio.to_thread(self.engine.quit)
            except Exception:
                logger.warning("Stockfish shutdown failed", exc_info=True)
        self.engine = await asyncio.to_thread(chess.engine.SimpleEngine.popen_uci, self.path)
        await asyncio.to_thread(self.engine.configure, {"Threads": 1, "Hash": 64})
        logger.info("Stockfish ready at %s", self.path)

    async def stop(self) -> None:
        async with self.lock:
            if self.engine is not None:
                await asyncio.to_thread(self.engine.quit)
                self.engine = None

    async def analyze(self, board: chess.Board, depth: int) -> EngineResult:
        async with self.lock:
            if self.engine is None:
                await self._restart_locked()
            assert self.engine is not None
            try:
                info = await asyncio.wait_for(asyncio.to_thread(self.engine.analyse, board, chess.engine.Limit(depth=depth)), timeout=8)
            except Exception:
                logger.warning("Stockfish analysis failed; restarting", exc_info=True)
                await self._restart_locked()
                assert self.engine is not None
                info = await asyncio.wait_for(asyncio.to_thread(self.engine.analyse, board, chess.engine.Limit(depth=depth)), timeout=8)
            if isinstance(info, list):
                info = info[0]
            return EngineResult(info["score"], info.get("pv", []), info.get("depth", depth))

    async def play(self, board: chess.Board, difficulty: str) -> tuple[chess.Move, EngineResult]:
        result = await self.analyze(board, DIFFICULTIES[difficulty]["depth"])
        if result.variation:
            return result.variation[0], result
        async with self.lock:
            assert self.engine is not None
            chosen = await asyncio.to_thread(self.engine.play, board, chess.engine.Limit(time=DIFFICULTIES[difficulty]["time"]))
        return chosen.move, result
