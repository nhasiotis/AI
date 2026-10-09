import { StrictMode, useEffect, useRef, useState } from "react";
import { Chess, Move } from "chess.js";
import { Chessboard } from "react-chessboard";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Color = "white" | "black";
type Difficulty = "beginner" | "easy" | "medium" | "hard" | "expert";
type Status = { state: string; winner: Color | null; inCheck: boolean };
type EvalItem = { type: string; value: number; display: string };
type AnalysisMove = { uci: string; san: string; toSquare: string; delta: EvalItem; before: EvalItem; after: EvalItem; principalVariation: string[]; depth: number };
type ApiResponse = { fen: string; status: Status; move?: { uci: string; san: string }; moves?: AnalysisMove[] };
type PositionEvaluation = { evaluation: EvalItem; depth: number };

const initialFen = new Chess().fen();

async function api<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  if (!response.ok) throw new Error((await response.json()).detail ?? "Request failed");
  return response.json() as Promise<T>;
}

function App() {
  const [fen, setFen] = useState(initialFen);
  const [humanColor, setHumanColor] = useState<Color>("white");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [selected, setSelected] = useState<string | null>(null);
  const [legalMoves, setLegalMoves] = useState<string[]>([]);
  const [analysis, setAnalysis] = useState<Record<string, AnalysisMove>>({});
  const [showEvaluation, setShowEvaluation] = useState(true);
  const [depth, setDepth] = useState(12);
  const [thinking, setThinking] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [positionEvaluation, setPositionEvaluation] = useState<EvalItem>({ type: "centipawn", value: 0, display: "0.00" });
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null);
  const [status, setStatus] = useState<Status>({ state: "playing", winner: null, inCheck: false });
  const [history, setHistory] = useState<string[]>([]);
  const [undoFen, setUndoFen] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const analysisController = useRef<AbortController | null>(null);
  const position = new Chess(fen);
  const computerTurn = position.turn() !== (humanColor === "white" ? "w" : "b");
  const gameActive = status.state === "playing" || status.state === "check";

  const clearSelection = () => { analysisController.current?.abort(); setSelected(null); setLegalMoves([]); setAnalysis({}); };

  useEffect(() => {
    if (!showEvaluation || !selected || !legalMoves.length || thinking || computerTurn) return;
    const controller = new AbortController();
    analysisController.current?.abort(); analysisController.current = controller;
    setAnalysisLoading(true);
    const requestedFen = fen;
    api<{ moves: AnalysisMove[] }>("/api/analysis/candidate-moves", { fen, fromSquare: selected, humanColor, depth, includePrincipalVariation: true }, controller.signal)
      .then((result) => { if (!controller.signal.aborted && requestedFen === fen) setAnalysis(Object.fromEntries(result.moves.map((item) => [item.toSquare, item]))); })
      .catch((error: Error) => { if (error.name !== "AbortError") setNotice(error.message); });
    return () => { controller.abort(); setAnalysisLoading(false); };
  }, [selected, fen, showEvaluation, depth, humanColor, thinking, computerTurn, legalMoves.length]);

  useEffect(() => {
    const controller = new AbortController();
    api<PositionEvaluation>("/api/analysis/position", { fen, humanColor }, controller.signal)
      .then((result) => { if (!controller.signal.aborted && result.evaluation) setPositionEvaluation(result.evaluation); })
      .catch((error: Error) => { if (error.name !== "AbortError") setNotice(error.message); });
    return () => controller.abort();
  }, [fen, humanColor]);

  useEffect(() => { if (humanColor === "black" && fen === initialFen) void makeComputerMove(fen); }, [humanColor]);

  function selectSquare(square: string) {
    if (thinking || !gameActive || computerTurn) return;
    if (selected && legalMoves.includes(square)) {
      requestMove(selected, square);
      return;
    }
    const moves = position.moves({ square: square as never, verbose: true }) as Move[];
    if (moves.length) { setSelected(square); setLegalMoves(moves.map((move) => move.to)); } else clearSelection();
  }

  function requestMove(from: string, to: string) {
    const move = position.moves({ square: from as never, verbose: true }).find((candidate) => candidate.to === to) as Move | undefined;
    if (!move) return;
    if (move.promotion) setPromotion({ from, to });
    else void submitPlayerMove(`${from}${to}`);
  }

  async function submitPlayerMove(uci: string) {
    setThinking(true); setUndoFen(fen); clearSelection();
    try {
      const result = await api<ApiResponse>("/api/game/player-move", { fen, uci, humanColor, difficulty });
      setFen(result.fen); setStatus(result.status); setHistory((items) => [...items, result.move?.san ?? ""]);
      if (result.status.state === "playing" || result.status.state === "check") await makeComputerMove(result.fen);
    } catch (error) { setNotice((error as Error).message); setThinking(false); }
  }

  async function makeComputerMove(currentFen: string) {
    setThinking(true);
    try {
      const result = await api<ApiResponse>("/api/game/computer-move", { fen: currentFen, humanColor, difficulty });
      setFen(result.fen); setStatus(result.status); setHistory((items) => [...items, result.move?.san ?? ""]);
    } catch (error) { setNotice((error as Error).message); }
    setThinking(false);
  }

  function handleDrop(source: string, target: string) {
    if (!thinking && !computerTurn && gameActive) requestMove(source, target);
    return true;
  }
  function newGame() { clearSelection(); setFen(initialFen); setStatus({ state: "playing", winner: null, inCheck: false }); setHistory([]); setUndoFen(null); setNotice(""); if (humanColor === "black") void makeComputerMove(initialFen); }
  function undo() { if (!undoFen || thinking) return; clearSelection(); setFen(undoFen); setUndoFen(null); setHistory((items) => items.slice(0, -2)); setStatus({ state: "playing", winner: null, inCheck: false }); }

  const overlays = Object.fromEntries(legalMoves.map((square) => [square, { background: analysis[square] ? (analysis[square].delta.value >= 5 ? "#4d9b7055" : analysis[square].delta.value <= -5 ? "#b95d5d66" : "#858b8a55") : "#d8c36a66", borderRadius: "50%" }]));
  const overlaySquares = legalMoves.map((square) => { const file = square.charCodeAt(0) - 97; const rank = Number(square[1]); return { square, left: `${(humanColor === "white" ? file : 7 - file) * 12.5}%`, top: `${(humanColor === "white" ? 8 - rank : rank - 1) * 12.5}%` }; });
  const whiteAdvantage = positionEvaluation.type === "mate" ? (positionEvaluation.value > 0 ? 100 : 0) : Math.max(-10, Math.min(10, positionEvaluation.value / 100));
  const whiteShare = 50 + whiteAdvantage * 5;
  const whiteDisplay = positionEvaluation.type === "mate" ? positionEvaluation.display : positionEvaluation.display;
  const blackValue = positionEvaluation.type === "mate" ? -positionEvaluation.value : -positionEvaluation.value;
  const blackDisplay = positionEvaluation.type === "mate" ? (blackValue > 0 ? "+Mate" : "-Mate") : `${blackValue / 100 >= 0 ? "+" : ""}${(blackValue / 100).toFixed(2)}`;

  return <main className="app-shell"><header className="topbar"><div><p className="eyebrow">CLASSICAL CHESS / STOCKFISH</p><h1>Make your move.</h1></div><div className="engine-state"><span className={`status-dot ${thinking ? "thinking" : "ready"}`} />{thinking ? "Stockfish thinking" : "Engine ready"}</div></header><div className="workspace"><section className="board-panel"><div className="board-with-eval"><div className="eval-scale"><span className="eval-label white-eval">{whiteDisplay}</span><div className="eval-track"><div className="eval-white" style={{ height: `${whiteShare}%` }} /><div className="eval-black" /></div><span className="eval-label black-eval">{blackDisplay}</span></div><div className="board-frame"><div className="board-wrap"><Chessboard position={fen} boardOrientation={humanColor} arePiecesDraggable={!thinking && !computerTurn && gameActive} onPieceDrop={handleDrop} onSquareClick={selectSquare} customSquareStyles={overlays} /><div className="eval-overlay">{overlaySquares.map(({ square, left, top }) => <span key={square} className={`eval-badge ${analysis[square] ? (analysis[square].delta.value >= 5 ? "positive" : analysis[square].delta.value <= -5 ? "negative" : "neutral") : "loading"}`} style={{ left, top }}>{analysis[square]?.delta.display ?? (analysisLoading ? "..." : "")}</span>)}</div></div></div></div><div className="board-caption"><strong>{status.state === "playing" ? (computerTurn || thinking ? "Stockfish is considering the position" : "Your turn") : status.state}</strong><span>{notice || (analysisLoading ? "Analyzing legal moves..." : "Engine estimates are approximate.")}</span></div></section><aside className="side-panel"><div className="control-row"><button onClick={newGame}>New game</button><button onClick={undo} disabled={!undoFen || thinking}>Undo</button><button className="quiet" onClick={() => { setStatus({ state: "resigned", winner: humanColor === "white" ? "black" : "white", inCheck: false }); clearSelection(); }}>Resign</button></div><section className="settings"><h2>Game setup</h2><label>Play as<select value={humanColor} onChange={(event) => { setHumanColor(event.target.value as Color); newGame(); }}><option value="white">White</option><option value="black">Black</option></select></label><label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as Difficulty)}>{["beginner", "easy", "medium", "hard", "expert"].map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label><label className="check"><input type="checkbox" checked={showEvaluation} onChange={(event) => { setShowEvaluation(event.target.checked); setAnalysis({}); }} />Show move evaluation adjustments</label><label>Analysis depth <input type="range" min="8" max="18" value={depth} onChange={(event) => setDepth(Number(event.target.value))} /><span className="range-value">{depth}</span></label></section><section className="history"><h2>Moves</h2>{history.length ? <ol>{Array.from({ length: Math.ceil(history.length / 2) }, (_, index) => <li key={index}><span>{history[index * 2] ?? ""}</span><span>{history[index * 2 + 1] ?? ""}</span></li>)}</ol> : <p>No moves yet.</p>}</section><section className="legend"><p><i className="green" /> Improves your position</p><p><i className="red" /> Worsens your position</p><p><i className="grey" /> Approximately equal</p></section></aside></div>{promotion && <div className="promotion-dialog" role="dialog"><div><h2>Choose promotion</h2>{["q", "r", "b", "n"].map((piece) => <button key={piece} onClick={() => { void submitPlayerMove(`${promotion.from}${promotion.to}${piece}`); setPromotion(null); }}>{piece === "q" ? "Queen" : piece === "r" ? "Rook" : piece === "b" ? "Bishop" : "Knight"}</button>)}</div></div>}</main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
