#!/usr/bin/env bash
# Pod bootstrap (runs ON THE POD as root, every start: the container disk is
# wiped on stop, only /workspace persists). Idempotent: safe to re-run.
#
#   LANE_LAYOUT=serial|shared|split  SAGE=0|1  GPU_NAME=...  GPU_RATE=...  bash /root/pod/bootstrap.sh
#   bash /root/pod/bootstrap.sh --restart-render    # relaunch only the render lane (e.g. toggle SAGE)
#   bash /root/pod/bootstrap.sh --restart-upworker  # relaunch only the upscale worker (requeues stale tickets)
#
# Expects /root/secrets.env (ANTHROPIC_API_KEY, COMFY_USER, COMFY_PASS) and the
# skill's pod/ + comfy_node/ copied to /root/pod/ by refswap_up.sh.
set -euo pipefail
LAYOUT="${LANE_LAYOUT:-serial}"; SAGE="${SAGE:-0}"
C=/workspace/ComfyUI; PY=/workspace/venv-clean/bin/python; POD=/root/pod
log() { echo "[bootstrap $(date +%H:%M:%S)] $*"; }

launch_lane() {   # name port cuda_devices extra_args...
  local name=$1 port=$2 dev=$3; shift 3
  tmux kill-session -t "$name" 2>/dev/null || true
  mkdir -p "/root/$name-temp" "/root/$name-user"
  local user_dir=$C/user
  [ "$name" = up ] && user_dir="/root/up-user"          # 2nd server must not share sqlite/user state
  tmux new-session -d -s "$name" "set -a; . /root/secrets.env; set +a; cd $C && \
    CUDA_VISIBLE_DEVICES=$dev $PY -u main.py --listen 127.0.0.1 --port $port \
    --temp-directory /root/$name-temp --user-directory $user_dir $* > /root/comfy_$name.log 2>&1"
}

wait_lane() {    # port name
  for i in $(seq 1 60); do
    curl -sf "http://127.0.0.1:$1/system_stats" >/dev/null && { log "$2 lane up on :$1 (${i}x5s)"; return 0; }
    pgrep -f "[m]ain.py.*--port $1" >/dev/null || { log "$2 lane DIED:"; tail -25 "/root/comfy_$2.log"; return 1; }
    sleep 5
  done
  log "$2 lane not answering after 300s"; tail -25 "/root/comfy_$2.log"; return 1
}

render_args() {
  local a=""
  [ "$SAGE" = 1 ] && a="$a --use-sage-attention"
  # shared GPU: keep headroom for the upscale lane's allocations
  [ "$LAYOUT" = shared ] && a="$a --reserve-vram ${RESERVE_VRAM_GB:-6}"
  echo "$a"
}

start_upworker() {
  local up=http://127.0.0.1:8189
  [ "$(python3 -c 'import json;print(json.load(open("/root/refswap_state.json")).get("layout","serial"))' 2>/dev/null)" != serial ] && up=http://127.0.0.1:8190
  tmux kill-session -t upworker 2>/dev/null || true
  tmux new-session -d -s upworker "$PY -u $POD/upscale_worker.py --host $up >> /root/upworker.log 2>&1"
  log "upscale worker (re)started on $up"
}

if [ "${1:-}" = "--restart-upworker" ]; then
  start_upworker; exit 0
fi

if [ "${1:-}" = "--restart-render" ]; then
  launch_lane render 8189 0 $(render_args); wait_lane 8189 render
  python3 - <<EOF
import json; p="/root/refswap_state.json"; s=json.load(open(p)); s["sage"]=int("$SAGE"); json.dump(s,open(p,"w"))
EOF
  exit 0
fi

[ -f /root/secrets.env ] || { log "missing /root/secrets.env"; exit 1; }
chmod 600 /root/secrets.env

# ---- 1. packages (container disk is fresh after every stop) ----------------
if ! command -v nginx >/dev/null || ! command -v htpasswd >/dev/null || ! command -v tmux >/dev/null; then
  log "apt: nginx apache2-utils tmux ffmpeg"
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx apache2-utils tmux ffmpeg >/dev/null
fi
$PY -c "import websocket" 2>/dev/null || $PY -m pip install -q "websocket-client>=1.6"
if [ "$SAGE" = 1 ] && ! $PY -c "import sageattention" 2>/dev/null; then
  log "pip: sageattention (lives in the venv on /workspace, so this is once)"
  $PY -m pip install -q sageattention || log "WARNING: sageattention install failed; SAGE runs will fall back"
fi

# ---- 2. custom node + workflow + SAM3 symlink ------------------------------
rm -rf "$C/custom_nodes/h3_prompt_director"
cp -r "$POD/comfy_node/h3_prompt_director" "$C/custom_nodes/"
mkdir -p "$C/user/default/workflows"
cp "$POD/h3_refswap.json" "$C/user/default/workflows/H3 Ref Character Replacement.json"
cp "$POD/upscale_run.py" /root/pod/upscale_run.py 2>/dev/null || true
M=$C/models
[ -e "$M/checkpoints/sam3.1_multiplex_fp16.safetensors" ] || \
  ln -s "$M/diffusion_models/sam3.1_multiplex_fp16.safetensors" "$M/checkpoints/sam3.1_multiplex_fp16.safetensors"
mkdir -p /workspace/batches

# ---- 3. nginx basic auth in front of the render lane ------------------------
. /root/secrets.env
cat > /etc/nginx/sites-enabled/comfy <<'NGX'
server {
  listen 8188;
  client_max_body_size 2g;
  auth_basic "ComfyUI";
  auth_basic_user_file /etc/nginx/.htpasswd;
  location / {
    proxy_pass http://127.0.0.1:8189;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
  }
}
NGX
# RunPod's image ships its own nginx.conf that never includes sites-enabled.
grep -q "include /etc/nginx/sites-enabled/\*;" /etc/nginx/nginx.conf || \
  sed -i '0,/http {/s//http {\n    include \/etc\/nginx\/sites-enabled\/*;/' /etc/nginx/nginx.conf
htpasswd -bc /etc/nginx/.htpasswd "$COMFY_USER" "$COMFY_PASS" >/dev/null 2>&1
chown "root:$(id -gn nobody)" /etc/nginx/.htpasswd; chmod 640 /etc/nginx/.htpasswd   # workers run as nobody
nginx -t -q && (nginx -s reload 2>/dev/null || nginx)

# ---- 4. lanes ---------------------------------------------------------------
NGPU=$(nvidia-smi -L | wc -l)
case "$LAYOUT" in
  serial) PORTS=8189 ;;
  shared) PORTS=8189,8190 ;;
  split)  [ "$NGPU" -ge 2 ] || { log "split needs 2 GPUs, found $NGPU"; exit 1; }; PORTS=8189,8190 ;;
  *) log "unknown LANE_LAYOUT=$LAYOUT"; exit 1 ;;
esac
launch_lane render 8189 0 $(render_args)
case "$LAYOUT" in
  shared) launch_lane up 8190 0 ;;
  split)  launch_lane up 8190 1 ;;
  serial) tmux kill-session -t up 2>/dev/null || true ;;
esac
wait_lane 8189 render
[ "$LAYOUT" != serial ] && wait_lane 8190 up

# ---- 5. state + helpers -----------------------------------------------------
python3 - <<EOF
import json, subprocess
gpu = subprocess.run(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],capture_output=True,text=True).stdout.strip().splitlines()
# GPU_NAME arrives as "?" when RunPod's REST omits machine.gpuTypeId (it did on
# 2026-09-28: every results row said gpu=?). Treat "?" as unknown -> nvidia-smi.
name = "${GPU_NAME:-}".strip()
name = name if name not in ("", "?") else (gpu[0] if gpu else "?")
json.dump({"layout":"$LAYOUT","sage":int("$SAGE"),"gpu":name,
           "gpu_count":len(gpu),"gpu_rate_per_hr":float("${GPU_RATE:-0}" or 0),"lane_ports":"$PORTS"},
          open("/root/refswap_state.json","w"), indent=1)
EOF
tmux has-session -t gpulog 2>/dev/null || tmux new-session -d -s gpulog "python3 $POD/gpu_log.py"
tmux kill-session -t autostop 2>/dev/null || true
rm -f /root/STOP_REQUESTED /root/SYNCED
tmux new-session -d -s autostop "LANE_PORTS=$PORTS python3 $POD/autostop.py"
start_upworker

# ---- 6. self-check ------------------------------------------------------------
curl -s http://127.0.0.1:8189/object_info/H3PromptDirector | grep -q H3PromptDirector && log "Director node loaded" || log "WARNING: Director node missing"
curl -s http://127.0.0.1:8189/object_info/H3AudioRoute | grep -q H3AudioRoute && log "AudioRoute node loaded" || log "WARNING: AudioRoute node missing"
[ "$SAGE" = 1 ] && { grep -i -m1 "sage" /root/comfy_render.log && log "(sage line above)" || log "WARNING: no 'sage' in render log; attention may not be using it"; }
A=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8188/)
B=$(curl -s -o /dev/null -w "%{http_code}" -u "x:wrong" http://127.0.0.1:8188/)
G=$(curl -s -o /dev/null -w "%{http_code}" -u "$COMFY_USER:$COMFY_PASS" http://127.0.0.1:8188/)
log "auth: none=$A wrong=$B right=$G (want 401/401/200)"
# Real proof, not "the env vars exist": an authenticated GET of this pod via
# the same code path self-stop uses. On 2026-09-28 the env-var check said True
# while every real stop call got 403 (default urllib User-Agent).
if python3 $POD/autostop.py --check; then SELFSTOP=ok; else SELFSTOP=FAIL; log "WARNING: pod cannot stop itself; only the local watcher can"; fi
log "READY layout=$LAYOUT sage=$SAGE ports=$PORTS selfstop=$SELFSTOP"
