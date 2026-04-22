# AI Analysis (Groq) — Phase-Wise Implementation Plan (On-Demand, Per Finding)

## Goal
Add an **AI explanation layer** that helps a non-expert understand each detected UB “time bomb”. The AI should:
- Explain **what the UB is** in the uploaded code.
- Explain **what changed between -O0 and -O2** using the LLVM IR diff + existing metrics.
- Explain **why the optimizer removed/rewrote code** (the UB assumption).
- Suggest **practical fixes** (and optionally a safer rewrite snippet).

**Important constraints (your choice):**
- AI is generated **per finding only**.
- AI is fetched **on demand** (user clicks a button).
- Groq **free API** is used (best quality available by default, with fallback).

---

## Architecture Overview
- Frontend already gets a report from `POST /analyze` that contains `findings[]` including:
  - `detail`, `fix`, `severity`, `metrics`, and the function IR (`finding.ir.O0` / `finding.ir.O2`).
- We will add a second backend endpoint:
  - `POST /ai-explain`
  - Input: selected finding (bounded) + optional source snippet.
  - Output: structured explanation JSON.
- Frontend adds a single button in the existing **Details** panel:
  - “Generate AI Explanation”
  - Shows loading/error
  - Renders explanation sections
  - Caches results per finding in-memory

---

## Phase 0 — Spec + Data Contract
### 0.1 Define the explanation schema (stable contract)
Backend returns:
```json
{
  "model": "llama-3.3-70b-versatile",
  "explanation": {
    "summary_plain": "...",
    "what_is_the_ub": "...",
    "what_changed_in_ir": "...",
    "why_optimizer_removed_code": "...",
    "fixes": ["...", "..."],
    "safer_rewrite": "...",
    "caveats": "..."
  }
}
```
Notes:
- `safer_rewrite` is optional (empty string or omitted when not appropriate).
- Keep everything as plain text (no markdown required), so UI rendering stays simple.

### 0.2 UI behavior
- Only for the **currently selected finding**.
- Only run when user clicks “Generate AI Explanation”.
- Show a small privacy note: “This sends code/IR excerpts to Groq.”

**Acceptance Criteria:**
- Contract is documented and used consistently by backend + frontend.

---

## Phase 1 — Backend: Groq Integration (Free + Best Quality)
### 1.1 Add dependency
- Add `httpx` (async HTTP client) to `requirements.txt`.

### 1.2 Add configuration (env vars)
- `GROQ_API_KEY` (**required** to enable)
- `GROQ_MODEL` (default: `llama-3.3-70b-versatile`)
- `GROQ_FALLBACK_MODEL` (default: `llama-3.1-8b-instant`)
- `GROQ_TIMEOUT_SECS` (default: `25`)
- `AI_EXPLAIN_MAX_CHARS` (default: `12000`)

**Why these models?**
- `llama-3.3-70b-versatile`: current production replacement for the older Llama 3 70B IDs.
- `llama-3.1-8b-instant`: current production replacement for the older Llama 3 8B IDs.

> Keep models configurable because Groq’s free catalog can change.

### 1.3 Implement Groq client wrapper
Create a module, e.g.:
- `backend/core/ai/groq_client.py`

Responsibilities:
- Build request for OpenAI-compatible endpoint:
  - `POST https://api.groq.com/openai/v1/chat/completions`
- Add `Authorization: Bearer $GROQ_API_KEY`
- Use strict timeouts and clear error messages.
- Implement a single retry path:
  - If response is 429 / timeout, retry once with fallback model.

**Acceptance Criteria:**
- Backend can call Groq successfully with local env vars.
- Missing/invalid key returns a helpful error.

---

## Phase 2 — Backend: Prompt + IR Diff Packaging
### 2.1 Build a “prompt payload” from a finding (bounded)
Create `backend/core/ai/prompt_builder.py` (or similar).

Inputs:
- `finding.category`, `finding.detail`, `finding.fix`, `finding.metrics`, `finding.confidence`
- `finding.ir.O0`, `finding.ir.O2`
- `finding.source_snippet` (already computed by report generator)

### 2.2 Generate compact IR context
- Compute unified diff of function IR:
  - Use Python `difflib.unified_diff`
- Truncate aggressively:
  - Keep at most e.g. 200–400 diff lines OR `AI_EXPLAIN_MAX_CHARS` total prompt
  - Prefer keeping:
    - function header
    - `ret` lines
    - `br` lines
    - `icmp` lines
    - arithmetic ops with flags like `nsw`

### 2.3 Prompt instructions (reliability)
System message should enforce:
- Explain to a beginner (no jargon without defining it).
- Do not invent facts not in input.
- Use the diff + metrics to justify claims.
- Output strict JSON with the schema from Phase 0.

### 2.4 Robust JSON parsing fallback
- Try `json.loads(content)`.
- If parsing fails:
  - Extract the first JSON object block `{...}` with a safe heuristic and retry.
  - If still fails: return `{ summary_plain: <raw text>, ... }` with other fields empty.

**Acceptance Criteria:**
- Prompt builder never exceeds size limits.
- Response parsing never crashes the API.

---

## Phase 3 — Backend: `POST /ai-explain` Endpoint
### 3.1 Add request/response models
In `backend/main.py`:
- `AIExplainRequest` with:
  - `finding: dict` (or a typed Pydantic model if you want strict validation)
  - `source_snippet: str | None` (optional; prefer snippet over full source)

### 3.2 Endpoint behavior
`POST /ai-explain`:
1. If `GROQ_API_KEY` missing → HTTP 503 with message “AI not configured”.
2. Validate payload size:
   - Reject huge IR blobs (HTTP 400).
3. Build prompt context.
4. Call Groq.
5. Return `{ model, explanation }`.

**Acceptance Criteria:**
- Works behind the existing Vite proxy (`/api/ai-explain` → backend `/ai-explain`).
- Returns fast and predictable errors for missing key / rate limits.

---

## Phase 4 — Frontend: On-Demand Explain Button (Per Finding)
### 4.1 Add a new hook
Create `frontend/src/hooks/useAIExplain.js` (or extend pattern):
- `explain(finding)` calls `POST /api/ai-explain`.
- Store `loading`, `error`.

### 4.2 Integrate into existing UI
Update `frontend/src/components/ReportPanel.jsx`:
- Add a button: “Generate AI Explanation”.
- Show:
  - Loading spinner
  - Error message
  - Returned explanation sections

### 4.3 Cache per finding
- Cache explanations in `App.jsx` or inside the hook.
- Cache key options:
  - `finding.function + finding.category + finding.metrics.blocks_O0 + blocks_O2 + ...`
  - or a stable hash of a subset of the finding.

**Acceptance Criteria:**
- Clicking the button triggers one network call.
- Switching between findings reuses cached explanation.

---

## Phase 5 — Testing + Docs
### 5.1 Backend tests (no real Groq)
Add tests under `backend/tests/`:
- Prompt truncation stays under `AI_EXPLAIN_MAX_CHARS`.
- JSON parsing fallback works.
- Endpoint returns 503 if key missing.
- Endpoint returns 200 with mocked `httpx` response.

### 5.2 README updates
Add a section:
- How to enable AI:
  - set `GROQ_API_KEY`
  - optionally set `GROQ_MODEL`
- Privacy note: code/IR excerpts are sent to Groq.

**Acceptance Criteria:**
- `pytest backend/tests -q` passes.
- Manual run works end-to-end.

---

## Minimal File/Code Change Checklist
Backend:
- `requirements.txt` → add `httpx`
- `backend/core/ai/groq_client.py` (new)
- `backend/core/ai/prompt_builder.py` (new)
- `backend/main.py` → add `POST /ai-explain`
- `backend/tests/test_ai_explain.py` (new)

Frontend:
- `frontend/src/hooks/useAIExplain.js` (new)
- `frontend/src/components/ReportPanel.jsx` → add button + render

Docs:
- `README.md` → Groq setup + privacy

---

## Manual Verification Script
1. Backend:
```powershell
$env:GROQ_API_KEY = "..."
$env:GROQ_MODEL = "llama-3.3-70b-versatile"
uvicorn backend.main:app --reload --port 8000
```
2. Frontend:
```powershell
cd frontend
npm install
npm run dev
```
3. In UI:
- Analyze a sample case.
- Select a finding.
- Click “Generate AI Explanation”.
- Confirm it explains UB, IR change, and fixes.
