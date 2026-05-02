#!/usr/bin/env bash
# Pretend "sysinfo" report. Uses only deterministic primitives.

cores=4
mem_mb=8192
uptime_s=12345

mem_gib=$(( mem_mb / 1024 ))
uptime_h=$(( uptime_s / 3600 ))
uptime_rest=$(( uptime_s % 3600 ))
uptime_m=$(( uptime_rest / 60 ))

printf 'cores: %d\n' "$cores"
printf 'memory: %d GiB\n' "$mem_gib"
printf 'uptime: %dh %dm\n' "$uptime_h" "$uptime_m"
