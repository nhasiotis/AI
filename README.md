# Chess MVP

A browser chess game for one human player against a local Stockfish engine. The backend is authoritative for legal moves and game status; the frontend provides the responsive board and interaction layer.

## Run locally

1. Install Docker Desktop and make sure its Linux engine is running.
2. From the repository root, run:

   ```sh
   docker compose up --build
   ```

3. Open [http://localhost:8080](http://localhost:8080).

The frontend container serves the built React application and proxies `/api` requests to FastAPI. Stockfish is installed and kept as a controlled process inside the backend container. The backend health endpoint is available at `/api/health`.

## Playing

Choose White or Black and a difficulty, then click or drag one of your pieces to a highlighted legal square. The backend validates every move before the position changes. When the evaluation setting is enabled, the selected piece's legal destinations are analyzed asynchronously. Green means the move improves the human position, red means it worsens it, and grey means the change is approximately equal.

Evaluation values are normalized to the human perspective before the delta is calculated:

```text
humanEvaluation = whiteEvaluation             when human is White
humanEvaluation = -whiteEvaluation            when human is Black
evaluationAdjustment = candidateEvaluation - baselineEvaluation
```

Values are displayed in pawns with two decimal places. Mate scores stay separate from centipawns and are shown as `M3`, `Mate`, or their signed equivalent.

## Development checks

Backend syntax can be checked with `python -m compileall -q backend`. With dependencies installed, run backend tests from `backend` using `pytest`. The frontend uses `npm run lint` and `npm run build`.

The default engine budgets are intentionally bounded for a laptop: one Stockfish thread, a 64 MB hash, and difficulty-dependent search depths. Candidate analysis is serialized through the same engine manager and requests are cancelled or ignored when the position changes.
