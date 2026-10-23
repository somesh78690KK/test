# T.A.R.O. - Comprehensive Security Review & Antivirus Compatibility

**Document Version:** 1.0.0  
**Tasks Addressed:** TASK-091, TASK-095  
**Review Scope:** Permissions, Sandbox Execution, Immutable Core Protection, Secrets Masking, Input Hooks, Antivirus / Windows Defender Considerations.

---

## 1. Security Architecture Summary

T.A.R.O. is designed around a zero-cloud-by-default, local-first paradigm with strict defensive boundaries:

1. **Risk-Classified Tool System:**
   - Tools are statically tagged with `RiskLevel`: `SAFE`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
   - Risk levels are hardcoded in Python definitions and cannot be altered by model prompts or LLM responses.
   - `HIGH` and `CRITICAL` risk tools (process termination, registry edits, system reboot, raw shell commands) require mandatory explicit confirmation (`ask_typed` phrase).
   - Autonomous scheduling of `HIGH` risk actions is strictly refused.

2. **Immutable Core Protection:**
   - Directories (`core/`) and permission definitions (`config/permissions.json`) are cryptographically protected via SHA-256 manifests (`data/core_manifest.json`).
   - Any runtime file operations (write, delete, move) targeting immutable paths are intercepted and blocked at the tool layer.
   - On application startup (`main.py`), a full integrity scan is performed. Any tampered file halts execution with an alert.
   - Windows ACLs can be locked down via `scripts/protect_install.bat`.

3. **Sandboxed Code Execution:**
   - Dynamic scripts and shell templates are strictly confined to the `sandbox/` directory.
   - Pre-execution AST security validation inspects all code for prohibited built-ins (`eval`, `exec`, `__import__`, `__builtins__`, `ctypes`, `winreg`).
   - Working directories are bound to `sandbox/`, and relative/absolute path traversal outside `sandbox/` is blocked.
   - Execution is bounded by a strict 30-second default timeout with guaranteed process killing.

4. **Secret Sanitization & Masking:**
   - All tool execution arguments, WebSocket frames, and log messages automatically mask sensitive parameters (`api_key`, `token`, `password`, `secret`).
   - External web outputs are wrapped in `<untrusted source="web">` tags, preventing prompt injection attacks from hijacking tool instructions.

5. **Kill-Switch Integration:**
   - Global emergency kill switch (`Ctrl+Alt+F12` or UI button) immediately aborts all running tools, kills spawned subprocesses, and prevents subsequent tool invocations.

---

## 2. Antivirus & Windows Defender Compatibility (TASK-095)

### Why Desktop AI Assistants Trigger Heuristics
T.A.R.O. interacts with the Windows OS using native APIs for:
- Global hotkey listening (`pynput`, `keyboard`).
- Mouse simulation and window inspection (`pywinauto`, `pywin32`, `UIAutomation`).
- Process enumeration (`psutil`).
- Subprocess execution within `sandbox/`.

Certain generic antivirus heuristic engines (e.g., Windows Defender SmartScreen, heuristic behavioral detectors) may flag input-hooking libraries or newly compiled PyInstaller binaries as `Trojan:Win32/Wacatac` or `HackTool:Win32/Keylogger`.

### Mitigations & Best Practices
1. **Local Compilation:** Build binaries on the target workstation using the provided PyInstaller spec (`taro.spec`). Locally generated executables match local user signatures.
2. **Exclusion / Allowlisting:**
   - If Windows Defender flags the virtual environment or PyInstaller output, add an exclusion for the installation directory:
     ```powershell
     Add-MpPreference -ExclusionPath "D:\T.A.R.O"
     ```
3. **Reproducible Code Signing:**
   - For enterprise deployment, sign `taro.exe` using a trusted code signing certificate:
     ```cmd
     signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 dist\taro.exe
     ```
4. **Input Hook Isolation:**
   - Input control (`system.input_control`) and hotkey registration run strictly through dedicated modular interfaces with rate limiting to avoid triggering anti-cheat or heuristic watchdog alarms.

---

## 3. Audited Vulnerability Findings & Resolutions

| ID | Component | Potential Risk | Status | Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Static AST Check | Introspection via `getattr(__builtins__, ...)` | **CLOSED** | Implemented AST visitor rules detecting `__builtins__` as `ast.Name` and checking `getattr` arguments against banned functions. |
| **SEC-02** | WebSocket Server | DNS Rebinding / Cross-Origin Hijack | **CLOSED** | Server binds to `127.0.0.1` only, validates `Host` header strictly against localhost, enforces token authentication, and rejects non-local `Origin`. |
| **SEC-03** | Shell Templates | Command Injection in Parametrized Templates | **CLOSED** | Regex parameter validator rejects metacharacters (`;`, `&`, `|`, `` ` ``, `$()`, `^`, `!`). Sandboxed cwd enforced. |
| **SEC-04** | Cloud Model Router | Data exfiltration via third-party APIs | **CLOSED** | Cloud routing disabled by default (`cloud.enabled: false`). Unauthorized cloud calls throw `CloudBlockedError`. Outgoing payloads are logged. |
| **SEC-05** | Core Files Tampering | Malicious modification of permission definitions | **CLOSED** | SHA-256 integrity verification at startup; runtime file tools intercept all operations targeting `core/` and `config/permissions.json`. |

---

## 4. Conclusion & Sign-Off
All security review requirements under **TASK-091** and **TASK-095** are met. T.A.R.O. provides robust local isolation, tamper resistance, and explicit user control.
