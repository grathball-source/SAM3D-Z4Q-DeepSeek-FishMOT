#!/usr/bin/env bash
# One-shot remote supervisor. The API key arrives through a mode-600 FIFO and is never saved.
set -uo pipefail
run=/home/xiongxiong/ehr1_event_history_20260926/run_v6
phase=${1:?phase required}
case "$phase" in b01|formal) ;; *) exit 2 ;; esac
IFS= read -r ehr1_key < "$run/key.pipe"
rm "$run/key.pipe"
printf '%s\n' "$ehr1_key" | bwrap --die-with-parent --unshare-all --share-net \
  --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
  --ro-bind /etc /etc --ro-bind /run/systemd/resolve /run/systemd/resolve \
  --dev-bind /dev /dev --proc /proc --tmpfs /tmp \
  --bind "$run/sender" /work --chdir /work /usr/bin/python3 sender.py "$phase" \
  > "$run/$phase.log" 2>&1
rc=$?
unset ehr1_key
printf '%s\n' "$rc" > "$run/$phase.exit"
exit "$rc"
