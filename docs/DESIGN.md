# T.A.R.O. - UI/UX and Persona Design

**Version:** 1.2.0 (Draft)

---

## 1. Persona

- **Name:** T.A.R.O. (Tactical Augmentation & Resource Orchestrator)
- **Voice:** Calm, precise, and brief. No filler, no greetings beyond the time-aware opener, no closing pleasantries.
- **Honesty rule:** States what it did and what the tool returned. If something failed, it says so and gives the exact error. It never says "done" before a tool result confirms it.
- **Refusal style:** Short and factual. It names the blocked action and the reason (permission level, risk, or missing tool), then offers the nearest allowed alternative.

Example:
> User: delete everything in my Downloads
> T.A.R.O.: Deleting files is HIGH risk. This would remove 214 items from C:\Users\...\Downloads. Say "confirm delete downloads" to proceed, or name specific files.

## 2. Layout (HUD, single agent)

```
┌──────────────────────────────────────────────────────────────┐
│ T.A.R.O.                     [Status: Listening] [Kill: ^!F12]│
├──────────────────────────────────────────────────────────────┤
│ CPU 22%  RAM 9.1/16 GB  GPU 41%  VRAM 4.2/6.0 GB  Net ↑ 12K │
├───────────────────────────────┬──────────────────────────────┤
│ Conversation                  │ Tool Activity                 │
│ You: open excel               │ 10:02:11 launch_app  OK       │
│ T.A.R.O.: Opened Excel.       │ 10:02:14 screen_ocr  OK 1.1s  │
│                               │ 10:02:20 file_write  AWAITING │
│                               │          [Confirm] [Deny]     │
├───────────────────────────────┴──────────────────────────────┤
│ [ Type a command or press mic ____________________ ] [Send]   │
└──────────────────────────────────────────────────────────────┘
```

Two columns replace the five-agent orbital layout. The orbital UI is removed, which saves GPU time and keeps idle GPU use low.

## 3. Components

### Status Indicators
- Idle: hollow grey dot.
- Listening: pulsing green dot.
- Thinking: spinning blue ring.
- Acting (tool running): amber bar with tool name.
- Awaiting confirmation: amber badge with Confirm and Deny buttons.
- Error: solid red dot with the error text.

### Tool Activity Panel
- One row per tool call: time, tool name, status, duration.
- Expand a row to see arguments (secrets masked) and the raw result.
- Confirmation rows stay pinned until answered.

### Confirmation Card
- Shows the exact action, risk level, target, and reason.
- Buttons: Confirm, Deny, Always allow this exact action (only for MEDIUM or below).
- For HIGH and CRITICAL, the card requires typing the confirmation phrase.

### Conversation
- User messages right-aligned, T.A.R.O. left-aligned.
- Code blocks have a copy button and language label.
- Mermaid diagrams render inline when requested.
- Auto-scroll unless the user scrolls up.

### Telemetry Bar
- Refreshes once per second. Values turn amber above 80% and red above 95%.
- VRAM bar shows a fixed 5.5 GB line (target ceiling).

### Input Bar
- Enter sends, Shift+Enter adds a line.
- Up/Down arrows cycle command history.
- Mic button toggles listening. Hold Space for push-to-talk when the input is focused.

### Settings Modal (tabs)
- General (wake word, greeting, theme), Voice, Vision and Camera, Models, Permissions, Skills, Workflows, Logs.

## 4. Colours

Carried over from J.A.R.V.I.E.S. V11 for continuity, with one accent.

| Token | Dark (default) | Light |
| :--- | :--- | :--- |
| `--bg` | `#010613` | `#f5f7fa` |
| `--surface` | `#0a1020` | `#ffffff` |
| `--border` | `#1a2a3a` | `#d5dde8` |
| `--text` | `#e0e0e0` | `#1c2430` |
| `--text-muted` | `#888888` | `#5f6b7a` |
| `--accent` | `#00ff88` | `#0066cc` |
| `--success` | `#00ff88` | `#11823b` |
| `--warning` | `#ffaa00` | `#b36b00` |
| `--error` | `#ff4444` | `#c62828` |
| `--info` | `#00aaff` | `#0066cc` |

Risk colours: SAFE grey, LOW green, MEDIUM amber, HIGH orange, CRITICAL red.

## 5. Typography

- UI: Segoe UI, Arial, sans-serif.
- Code and logs: Cascadia Code, Consolas, monospace.
- Sizes: H1 24px, H2 18px, H3 14px, body 13px, small 11px, code 12px.
- Weights: 400 body, 600 headings. No all-caps headings except the wordmark.

## 6. Voice States

| State | Visual | Audio |
| :--- | :--- | :--- |
| Waiting for wake word | Grey dot | None |
| Wake word heard | Green flash | Short chime |
| Recording command | Waveform bar | None |
| Speaking reply | Accent waveform | TTS audio |
| Mic muted | Red slash on mic | None |

Speech output can be turned off per session. Confirmation prompts are always shown on screen, even when TTS is on.

## 7. Interaction

- Keyboard first. Every action reachable without a mouse.
- Shortcuts: Ctrl+L clear view, Ctrl+, settings, Ctrl+H help, Ctrl+Q quit, F1 docs, Ctrl+Alt+F12 kill switch (global).
- Hover: buttons brighten, cards show a 1px accent border.
- Focus ring: 2px accent outline, never removed.

## 8. Feedback and Errors

- Every action shows an immediate state change (Acting) before the result.
- Errors show: what failed, the exact tool error, and one suggested next step. No vague "something went wrong".
- Long operations (over 3 s) show elapsed time and a Cancel button.

## 9. Accessibility

- WCAG 2.1 AA contrast: 4.5:1 for body text, 3:1 for large text and icons.
- All controls have ARIA labels. Status changes are announced via aria-live (polite for info, assertive for confirmations).
- Supports 200% text scaling without horizontal scrolling.
- Screen-reader-readable confirmation cards.

## 10. Responsiveness

- Minimum window 800 x 600. Recommended 1200 x 800.
- Below 1000 px wide, the two columns stack (conversation on top, tool activity below, collapsible).
- Respects Windows DPI scaling.

## 11. Motion

- Transitions 200 to 300 ms ease-in-out.
- Motion is reduced when the Windows "reduce motion" setting is on.
- No decorative animation during tool execution.

## 12. Required UI Elements for Safety

These elements must exist because other docs depend on them.

- **Kill button:** always visible in the status bar and in the system tray menu (the global hotkey cannot be received while an admin-level window has focus).
- **Recording indicator:** a red dot and the text "Recording" whenever training mode records input.
- **Untrusted-content line:** the confirmation card shows "This request involved content from <source>." when ARCHITECTURE section 23 applies, and highlights text copied from that source.
- **Status block:** every reply ends with a code-generated list of actions and their statuses. It uses a monospace style so it is not confused with the model's wording.
- **Service toggles:** Security Guardian, Notification Guardian, and Screen Watcher each show state (off, running, unsupported) in Settings.
- **Prerequisite panel:** shows `taro.doctor` results (Ollama, models, Tesseract, WebView2, Playwright, VRAM) with the fix for each failed item.
