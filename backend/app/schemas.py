from typing import Literal

from pydantic import BaseModel, Field

Color = Literal["white", "black"]
Difficulty = Literal["beginner", "easy", "medium", "hard", "expert"]


class NewGameRequest(BaseModel):
    humanColor: Color = "white"
    difficulty: Difficulty = "medium"


class PositionRequest(BaseModel):
    fen: str = Field(min_length=10, max_length=120)
    humanColor: Color


class PlayerMoveRequest(PositionRequest):
    uci: str = Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$", max_length=5)
    difficulty: Difficulty = "medium"


class ComputerMoveRequest(PositionRequest):
    difficulty: Difficulty = "medium"


class CandidateAnalysisRequest(PositionRequest):
    fromSquare: str = Field(pattern=r"^[a-h][1-8]$")
    depth: int = Field(default=13, ge=8, le=18)
    includePrincipalVariation: bool = True
