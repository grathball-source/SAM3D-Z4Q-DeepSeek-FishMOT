#!/usr/bin/env bash
# A phase consumes a fresh mode-600 FIFO; the key is neither an argument nor a file.
set -uo pipefail
run=/home/xiongxiong/ehr1r_causal_history_20260926/run_v5
phase=${1:?phase required}
case "$phase" in smoke|b01|formal) ;; *) exit 2 ;; esac
IFS= read -r ehr1r_key < "$run/key.pipe"
rm "$run/key.pipe"
printf '%s\n' "$ehr1r_key" | bwrap --die-with-parent --unshare-all --share-net \
  --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
  --ro-bind /etc /etc --ro-bind /run/systemd/resolve /run/systemd/resolve \
  --dev-bind /dev /dev --proc /proc --tmpfs /tmp \
  --bind "$run/sender" /work --chdir /work /usr/bin/python3 sender.py "$phase" \
  > "$run/$phase.log" 2>&1
rc=$?
unset ehr1r_key
printf '%s\n' "$rc" > "$run/$phase.exit"
exit "$rc"
