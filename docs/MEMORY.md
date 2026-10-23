# T.A.R.O. - Memory and Context Design

**Version:** 1.2.0 (Draft)

---

## 1. Goals

1. The user should not repeat stable facts (name, machine, preferences, project names).
2. Long sessions must not overflow the 4096-token context window.
3. Memory must be editable and deletable by the user.
4. Memory must stay local.

## 2. Context Window Strategy

The chat model runs with `num_ctx = 4096`. Every turn builds a prompt from fixed-budget sections (ARCHITECTURE section 6.4):

| Section | Budget (tokens) | Source |
| :--- | :--- | :--- |
| System prompt | 600 | `config/persona.md` (versioned) |
| Tool schemas | 900 | Registry, filtered by category |
| Profile + recalled memory | 400 | `profile.md`, ChromaDB top-k |
| Rolling summary | 400 | SQLite `summaries` |
| Recent turns | 1200 | SQLite `turns`, newest first |
| Response reserve | 596 | Output |

If a section exceeds its budget, it is truncated from the oldest end (turns, memory) or lowest rank (recalled memory). The truncation is logged.

### Summary Cycle

- Every 5 completed turns, the summarizer rewrites the rolling summary using the previous summary plus the 5 new turns.
- Summary target length: 250 to 350 tokens.
- Summary keeps: user goals, decisions, open tasks, file paths touched, and any confirmed preferences.
- Summary drops: small talk, failed tool details that were later resolved, raw tool output.

## 3. Memory Tiers

### Tier 1 - Short-Term (SQLite `data/taro.db`)

| Table | Columns | Purpose |
| :--- | :--- | :--- |
| `sessions` | id, started_at, ended_at | Session boundaries |
| `turns` | id, session_id, role, content, created_at, tokens | Conversation |
| `tool_calls` | id, turn_id, tool, args_masked, status, output_ref, duration_ms | Tool history |
| `summaries` | id, session_id, text, covers_turns, created_at | Rolling summaries |
| `plans` | id, turn_id, steps_json, status | Multi-step plans |

Retention: 90 days by default. `output_ref` points to a file under `logs/` when output is large, so the table stays small.

### Tier 2 - Long-Term Semantic (ChromaDB `data/chroma/`)

Collections:

| Collection | Contents | Written when |
| :--- | :--- | :--- |
| `facts` | Stable facts the user stated ("my laptop has 6 GB VRAM") | User states it, or user confirms a suggested fact |
| `preferences` | How the user wants T.A.R.O. to behave ("short answers") | User states it |
| `notes` | Notes created with the notes tool | Note tool call |
| `documents` | Chunks of files the user asks T.A.R.O. to index | User asks to index a folder |

Each record stores: `text`, `created_at`, `source` (user, tool, or document path), `confidence` (1.0 for stated facts), and `last_used_at`.

Recall: top 4 results above similarity 0.35, with the source shown to the model.

### Tier 3 - Procedural (JSON `data/procedural/`)

| File | Contents |
| :--- | :--- |
| `workflows/<name>.json` | Recorded and compiled workflows (steps, expected windows, success count) |
| `trusted_actions.json` | Approved action patterns (pattern, scope, approved_at, revocable) |
| `permission_log.json` | Permission decisions (action, decision, timestamp, risk) |

JSON is used for records that need to be read and edited by hand.

## 4. Profile (`data/profile.md`)

Plain markdown the user owns. T.A.R.O. reads it every session and may propose edits; it writes only after the user confirms.

Template:

```markdown
# Profile

- Name:
- Preferred name for T.A.R.O.:
- Machine: Ryzen 5 6600H, RTX 4050 6GB, 16 GB RAM
- Language(s):
- Preferred reply length: short
- Voice: on / off
- Projects I am working on:
```

Rules:
- Only fields the user has filled in are sent to the model.
- Empty fields are not included in the prompt.
- Projects listed here are used for recall only when the user mentions them.

## 5. What Gets Stored

| Stored | Not stored |
| :--- | :--- |
| Facts the user states | Inferred personality traits or emotional state |
| Preferences the user states | Health, finances, or sensitive data unless the user explicitly asks to store it |
| Tool calls (args masked) | Passwords, API keys, tokens |
| Summaries of conversations | Raw screenshots or camera frames |
| Confirmed trusted actions | Unconfirmed guesses about the user |

Sensitive categories (health, finances, identity, relationships) follow the same rule: store only when the user explicitly asks, and show the entry in the HUD memory viewer.

## 6. Write Rules

1. The model proposes a memory write as a tool call (`memory_save`). The user sees a one-line notice in Tool Activity. Stated facts from the user are saved without a confirmation prompt; anything inferred needs a confirmation.
2. Each memory record gets one source. Duplicates are merged when the new text is more than 90% similar (cosine distance check before insert).
3. Corrections replace the old record. The old record is kept for 30 days in a `superseded` state, then deleted.
4. Writes are logged in the audit trail with the record ID.

## 7. Read Rules

1. The orchestrator recalls memory only when the request is about the user, their files, their projects, or a past conversation. Pure general-knowledge questions skip recall.
2. Recalled items are shown to the model with source and date. The model must cite the source when it uses a recalled fact ("from your profile").
3. Recalled items are never shown to the user unless the user asks what T.A.R.O. remembers.
4. Sensitive memory categories are not recalled unless the request is directly about that topic.

## 8. User Controls

Available in the HUD Memory tab (TASK-087):
- Browse by store and collection.
- Search (keyword and semantic).
- Edit or delete one record.
- Delete all memory for a topic (removes matching records across all three tiers).
- Export to JSON.
- Pause memory writes (session-only mode, nothing saved until resumed).
- Clear all memory (requires typed confirmation).

## 9. Privacy

- All memory is local. No sync, no cloud upload.
- Cloud features (image generation, Gemini override) send only the prompt the user approved for that request, never the memory store.
- Memory files are not included in logs.

## 10. Backup

- Manual export from the HUD writes a zip of `data/` (excluding `chroma/` index files, which are rebuilt).
- Automatic daily SQLite backup to `data/backups/`, keeping the last 7.

## 11. Testing

- Round-trip tests for each store (TASK-060).
- Budget test: 50 turns and 30 summaries stay under 4096 tokens (TASK-014, TASK-015).
- Deletion test: deleting a topic removes all three tiers (TASK-087).
- Redaction test: a secret in a tool argument never appears in SQLite or logs.

## 12. Embeddings Must Work Offline

ChromaDB's default embedding function downloads a model from the internet on first use. That breaks the offline promise and fails on a machine with no network. Fix:

- Use a **bundled local embedding model**. Default: the all-MiniLM-L6-v2 ONNX model shipped inside the app's `models/` folder (about 90 MB), loaded with an explicit embedding function so Chroma never tries to download.
- Alternative: an Ollama embedding model such as `nomic-embed-text`, run on CPU (`num_gpu 0`) so it does not take VRAM.
- Acceptance test (TASK-060): with the network adapter disabled, writing and searching memory must still work.
- The embedding model name and version are stored in the collection metadata. Changing the model requires re-embedding; T.A.R.O. detects a mismatch at startup and offers to rebuild instead of returning wrong results.

## 13. Storage Failure Handling

| Failure | Behaviour |
| :--- | :--- |
| SQLite locked or corrupt | Retry twice, then open a fresh session DB, keep the broken file as `taro.db.corrupt`, tell the user |
| ChromaDB index damaged | Rebuild from SQLite `facts` and `notes` tables (SQLite holds the source text for every Tier 2 record) |
| Disk full | Stop writes, keep answering, show a persistent warning in the HUD |
| Profile file missing | Recreate from the template |
| Embedding model mismatch | Offer a rebuild; do not search with a mismatched model |
