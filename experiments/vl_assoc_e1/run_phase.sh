#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
phase="$1"
shift
case "$phase" in smoke|formal) ;; *) exit 2 ;; esac
run_dir=${E1_RUN_ID:-api_run_20260923}
case "$run_dir" in api_run_20260923|api_rerun_20260923_default64k) ;; *) exit 2 ;; esac
test ! -e "$run_dir/${phase}.log" || exit 3
test ! -e "$run_dir/${phase}_exit_code.txt" || exit 3
umask 077
export CUDA_VISIBLE_DEVICES=
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2
: "${E1_PYTHON:?set E1_PYTHON to the verified task interpreter}"
"$E1_PYTHON" e1_execute.py "$phase" "$@" > "$run_dir/${phase}.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$run_dir/${phase}_exit_code.txt"
exit "$rc"
