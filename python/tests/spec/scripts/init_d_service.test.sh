#!/usr/bin/env bash
# Classic /etc/init.d/foo style service script with start/stop/status/restart.

NAME=demo
PIDFILE=/tmp/$NAME.pid

# Simulate: pid file presence == "running".
status() {
  if [[ -f "$PIDFILE" ]]; then
    echo "$NAME is running (pid $(cat "$PIDFILE"))"
    return 0
  fi
  echo "$NAME is stopped"
  return 3
}

start() {
  if [[ -f "$PIDFILE" ]]; then
    echo "$NAME already running"
    return 1
  fi
  echo 4242 > "$PIDFILE"
  echo "$NAME started"
}

stop() {
  if [[ ! -f "$PIDFILE" ]]; then
    echo "$NAME not running"
    return 1
  fi
  rm -f "$PIDFILE"
  echo "$NAME stopped"
}

restart() {
  stop || true
  start
}

# Drive the whole life-cycle.
for action in status start status start restart status stop status; do
  echo "-- $action --"
  case "$action" in
    start) start ;;
    stop) stop ;;
    status) status; echo "rc=$?" ;;
    restart) restart ;;
  esac
done
