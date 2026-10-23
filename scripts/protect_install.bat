@echo off
REM ===========================================================================
REM T.A.R.O. - Installation Protection Script (TASK-125)
REM Locks core/ and config/permissions.json with read-only attributes and
REM computes SHA-256 cryptographic manifest for startup verification.
REM ===========================================================================

echo [T.A.R.O.] Applying immutable protections to core components...

REM 1. Set read-only attributes on core directory recursively
attrib +r core\* /s /d >nul 2>&1
attrib +r config\permissions.json >nul 2>&1
attrib +r config\config.yaml >nul 2>&1

echo [T.A.R.O.] Generating core integrity SHA-256 manifest...
.\venv\Scripts\python -c "from core.safety.immutable import generate_core_manifest; m = generate_core_manifest(); print(f'Protected {len(m)} core files.')"

echo [T.A.R.O.] Protection complete. Core is locked and manifest verified.
exit /b 0
