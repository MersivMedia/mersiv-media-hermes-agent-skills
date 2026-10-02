"""Live-test a CLI's .env loading with a real key, without ever exposing the key.

Usage (edit the CONFIG block, then run bare: `python3 live_envfile_check.py`):
  - the key is read from SOURCE_ENV inside this process (never argv, never printed)
  - written into a throwaway .env (mode 600) in a temp dir
  - the CLI runs with every key var stripped from the child env, so .env is the only source
  - all output is scanned for the key and masked; exit 1 if it ever appears
  - a --no-env-file control run must FAIL (proves the key came from .env)
  - the temp dir is removed in `finally`
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

# ---- CONFIG ---------------------------------------------------------------
CLI = str(pathlib.Path.home() / "<tool-dir>/.venv/bin/<tool>")
SOURCE_ENV = pathlib.Path.home() / ".hermes/.env"
KEY_VAR = "AI_GATEWAY_API_KEY"
STRIP_VARS = {"AI_GATEWAY_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"}
INIT_ARGS = ["init", "--store", "memory", "--embedder", "gateway:openai/text-embedding-3-small"]
COMMANDS = [["check"]]                      # add ingest/query steps as needed
CONTROL = ["--no-env-file", "check"]        # must exit non-zero
NOISE = ("UserWarning", "warnings.warn", "Exception ignored", "  File ", "Traceback")
# ---------------------------------------------------------------------------

key = next((line.split("=", 1)[1].strip().strip('"').strip("'")
            for line in SOURCE_ENV.read_text().splitlines() if line.startswith(f"{KEY_VAR}=")), "")
if not key:
    sys.exit(f"{KEY_VAR} not found in {SOURCE_ENV}")

tmp = pathlib.Path(tempfile.mkdtemp(prefix="envfile_live_"))
child_env = {k: v for k, v in os.environ.items() if k not in STRIP_VARS}
leaked = False


def run(args):
    global leaked
    r = subprocess.run([CLI, *args], cwd=tmp, env=child_env, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    if key in out:
        leaked = True
        out = out.replace(key, "[REDACTED]")
    print(f"$ {' '.join(args)}   (exit {r.returncode})")
    print("\n".join("  " + ln for ln in out.splitlines() if not any(s in ln for s in NOISE)))
    return r.returncode


try:
    run(INIT_ARGS)
    envf = tmp / ".env"
    text = envf.read_text()
    marker = f"\n{KEY_VAR}=\n"
    assert marker in text, f"blank {KEY_VAR}= line not found in generated .env"
    envf.write_text(text.replace(marker, f"\n{KEY_VAR}={key}\n", 1))
    envf.chmod(0o600)
    print(f"child env has a key: {any(v in child_env for v in STRIP_VARS)}; .env mode {oct(envf.stat().st_mode & 0o777)}")
    codes = [run(c) for c in COMMANDS]
    control = run(CONTROL)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"temp dir removed: {not tmp.exists()}")
print(f"key appeared in any output: {leaked}")
print(f"exit codes: {codes}  control (should be non-zero): {control}")
sys.exit(1 if leaked or any(codes) or control == 0 else 0)
