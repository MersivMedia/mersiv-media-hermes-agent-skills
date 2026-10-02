#!/usr/bin/env bash
# Pod-side status word for one batch (runs ON THE POD; called by perf_session's
# wait_batch over ssh). Prints exactly one line:
#   DONE                                  runner gone and no pending upscale tickets
#   WORKER_DEAD tickets=N hb=Ss           tickets pending but the upscale worker
#                                         is gone or its heartbeat is stale
#   BUSY runner=0|1 tickets=N worker=0|1
#   bash /root/pod/batch_status.sh <batch-name>
B=${REFSWAP_BATCHES:-/workspace/batches}/$1
Q=$B/upscale_queue
RUNDIR=${REFSWAP_RUNDIR:-/root}
HB_MAX=${HB_MAX:-120}
r=0; pgrep -f "[b]atch_runner.py $B" >/dev/null && r=1
t=$(ls "$Q"/*.json "$Q"/*.json.working 2>/dev/null | wc -l)
w=0; pgrep -f "[u]pscale_worker.py" >/dev/null && w=1
hb=$(( $(date +%s) - $(cat "$RUNDIR/upworker.alive" 2>/dev/null || echo 0) ))
if [ "$r" = 0 ] && [ "$t" = 0 ]; then echo DONE
elif [ "$t" -gt 0 ] && { [ "$w" = 0 ] || [ "$hb" -gt "$HB_MAX" ]; }; then echo "WORKER_DEAD tickets=$t hb=${hb}s"
else echo "BUSY runner=$r tickets=$t worker=$w"; fi
