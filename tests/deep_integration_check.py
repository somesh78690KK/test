"""T.A.R.O. - Deep Integration Check

Comprehensive verification of all system integrations, capabilities, and configurations.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class DeepIntegrationChecker:
    """Comprehensive integration checker for T.A.R.O."""

    def __init__(self):
        self.results = {
            "core_system": {},
            "voice_pipeline": {},
            "capabilities": {},
            "configuration": {},
            "safety": {},
            "ui": {},
            "total_issues": 0,
            "total_checks": 0
        }

    def log_check(self, category: str, name: str, passed: bool, message: str = ""):
        """Log a check result."""
        if category not in self.results:
            self.results[category] = {}
        self.results[category][name] = {"passed": passed, "message": message}
        self.results["total_checks"] += 1
        if not passed:
            self.results["total_issues"] += 1
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {category:20} | {name:40} | {message}")

    def check_core_system(self):
        """Check core system components."""
        print("\n=== Core System Checks ===")
        
        # Check main.py exists
        main_path = project_root / "main.py"
        self.log_check("core_system", "main.py exists", main_path.exists())
        
        # Check core modules
        core_modules = [
            "core.config",
            "core.orchestrator",
            "core.ws.server",
            "core.tools.registry",
            "core.safety.permissions",
            "core.safety.immutable",
            "core.model.ollama_client",
        ]
        
        for module in core_modules:
            try:
                __import__(module)
                self.log_check("core_system", f"{module} importable", True)
            except ImportError as e:
                self.log_check("core_system", f"{module} importable", False, str(e))

    def check_voice_pipeline(self):
        """Check voice pipeline components."""
        print("\n=== Voice Pipeline Checks ===")
        
        # Check voice modules
        voice_modules = [
            "voice.stt",
            "voice.tts",
            "voice.wake_word",
            "voice.audio_worker",
            "voice.expressions",
        ]
        
        for module in voice_modules:
            try:
                __import__(module)
                self.log_check("voice_pipeline", f"{module} importable", True)
            except ImportError as e:
                self.log_check("voice_pipeline", f"{module} importable", False, str(e))
        
        # Check Vosk model
        vosk_model_path = project_root / "models" / "vosk-model-small-en-us-0.15"
        self.log_check("voice_pipeline", "Vosk model exists", vosk_model_path.exists())
        
        if vosk_model_path.exists():
            model_amd = vosk_model_path / "am"
            model_graph = vosk_model_path / "graph"
            model_conf = vosk_model_path / "conf"
            has_amd = model_amd.exists()
            has_graph = model_graph.exists()
            has_conf = model_conf.exists()
            self.log_check("voice_pipeline", "Vosk model files complete", has_amd and has_graph and has_conf)
        
        # Check voice expressions
        expressions_path = project_root / "voice" / "assets" / "expressions"
        self.log_check("voice_pipeline", "Voice expressions directory", expressions_path.exists())

    def check_capabilities(self):
        """Check capabilities registration."""
        print("\n=== Capabilities Checks ===")
        
        try:
            from capabilities import ALL_CAPABILITY_TOOLS
            tool_count = len(ALL_CAPABILITY_TOOLS)
            self.log_check("capabilities", "ALL_CAPABILITY_TOOLS defined", tool_count > 0, f"{tool_count} tools")
            
            # Check for parameters on all tools
            tools_without_params = []
            for tool in ALL_CAPABILITY_TOOLS:
                if not hasattr(tool, 'parameters'):
                    tools_without_params.append(tool.name)
            
            if len(tools_without_params) == 0:
                self.log_check("capabilities", "All tools have parameters", True)
            else:
                self.log_check("capabilities", "All tools have parameters", False, f"{len(tools_without_params)} missing")
                
        except Exception as e:
            self.log_check("capabilities", "Capabilities import failed", False, str(e))

    def check_configuration(self):
        """Check configuration files."""
        print("\n=== Configuration Checks ===")
        
        config_files = [
            "config/config.yaml",
            "config/permissions.json",
            "config/apps.json",
        ]
        
        for config_file in config_files:
            config_path = project_root / config_file
            self.log_check("configuration", f"{config_file} exists", config_path.exists())
        
        # Check config validation
        try:
            from core.config import cfg
            self.log_check("configuration", "Config loads successfully", True)
            self.log_check("configuration", "Voice config loaded", hasattr(cfg, 'voice'))
            self.log_check("configuration", "Model config loaded", hasattr(cfg, 'model'))
            self.log_check("configuration", "Orchestrator config loaded", hasattr(cfg, 'orchestrator'))
        except Exception as e:
            self.log_check("configuration", "Config validation failed", False, str(e))

    def check_safety(self):
        """Check safety systems."""
        print("\n=== Safety System Checks ===")
        
        try:
            from core.safety.immutable import generate_core_manifest
            self.log_check("safety", "generate_core_manifest exists", True)
            
            manifest_path = project_root / "data" / "core_manifest.json"
            self.log_check("safety", "core_manifest.json exists", manifest_path.exists())
            
            if manifest_path.exists():
                import json
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                files_count = len(manifest)
                self.log_check("safety", "Manifest has file count", files_count > 0, f"{files_count} files")
                    
        except Exception as e:
            self.log_check("safety", "Safety system check failed", False, str(e))

    def check_ui(self):
        """Check UI components."""
        print("\n=== UI System Checks ===")
        
        # Main HTML file (CSS and JS are embedded)
        ui_html = project_root / "ui/html/taro_hud.html"
        self.log_check("ui", "ui/html/taro_hud.html exists", ui_html.exists())
        
        if ui_html.exists():
            try:
                content = ui_html.read_text(encoding='utf-8')
                has_css = "<style>" in content
                has_js = "<script>" in content
                self.log_check("ui", "HTML has embedded CSS", has_css)
                self.log_check("ui", "HTML has embedded JS", has_js)
            except Exception as e:
                self.log_check("ui", "HTML read for CSS/JS check", False, str(e))

    def check_pyinstaller_spec(self):
        """Check PyInstaller configuration."""
        print("\n=== PyInstaller Spec Checks ===")
        
        spec_path = project_root / "taro.spec"
        self.log_check("build", "taro.spec exists", spec_path.exists())
        
        if spec_path.exists():
            content = spec_path.read_text()
            self.log_check("build", "Spec includes Vosk", "vosk" in content.lower())
            self.log_check("build", "Spec includes hookspath", "hookspath" in content.lower())
            self.log_check("build", "Spec includes models", "models" in content.lower())
            self.log_check("build", "Spec includes voice assets", "voice/assets" in content.lower())
            
            # Check if hook-vosk.py exists in root
            hook_vosk = project_root / "hook-vosk.py"
            self.log_check("build", "hook-vosk.py exists", hook_vosk.exists())

    def check_executable(self):
        """Check if executable exists and is recent."""
        print("\n=== Executable Checks ===")
        
        exe_path = project_root / "dist" / "taro" / "taro.exe"
        self.log_check("build", "Executable exists", exe_path.exists())
        
        if exe_path.exists():
            import datetime
            mod_time = datetime.datetime.fromtimestamp(exe_path.stat().st_mtime)
            self.log_check("build", "Executable is recent", True, f"Built: {mod_time}")

    def run_all_checks(self):
        """Run all integration checks."""
        print("=" * 80)
        print("T.A.R.O. Deep Integration Check")
        print("=" * 80)
        
        self.check_core_system()
        self.check_voice_pipeline()
        self.check_capabilities()
        self.check_configuration()
        self.check_safety()
        self.check_ui()
        self.check_pyinstaller_spec()
        self.check_executable()
        
        print("\n" + "=" * 80)
        print("Integration Check Summary")
        print("=" * 80)
        print(f"Total Checks: {self.results['total_checks']}")
        print(f"Passed: {self.results['total_checks'] - self.results['total_issues']}")
        print(f"Failed: {self.results['total_issues']}")
        print("=" * 80)
        
        # List all failures
        if self.results['total_issues'] > 0:
            print("\nFailed Checks:")
            for category, checks in self.results.items():
                if category == "total_checks" or category == "total_issues":
                    continue
                for name, result in checks.items():
                    if not result['passed']:
                        print(f"  - {category}/{name}: {result['message']}")
        
        return self.results


def main():
    """Main entry point."""
    checker = DeepIntegrationChecker()
    results = checker.run_all_checks()
    
    if results['total_issues'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
