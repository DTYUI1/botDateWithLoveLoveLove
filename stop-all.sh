#!/bin/bash
# Остановка ConnectMe бота и backend, запущенных через start-all.sh
set -u

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"
RUN_DIR="$PROJECT_ROOT/.run"

QUIET=0
if [ "${1:-}" = "--quiet" ]; then
    QUIET=1
fi

log() {
    if [ "$QUIET" -eq 0 ]; then
        echo "$@"
    fi
}

stop_pidfile() {
    local name="$1"
    local pidfile="$RUN_DIR/$name.pid"
    if [ ! -f "$pidfile" ]; then
        log "[stop] $name: pid-файл не найден ($pidfile) — пропускаю."
        return 0
    fi
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -z "$pid" ]; then
        rm -f "$pidfile"
        return 0
    fi
    if kill -0 "$pid" 2>/dev/null; then
        log "[stop] $name: завершаю PID $pid (SIGTERM)"
        kill -TERM "$pid" 2>/dev/null || true
        for i in {1..15}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.5
        done
        if kill -0 "$pid" 2>/dev/null; then
            log "[stop] $name: не отвечает, посылаю SIGKILL"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    else
        log "[stop] $name: PID $pid уже не работает"
    fi
    rm -f "$pidfile"
}

# Бота гасим первым — чтобы он не пытался дёргать backend во время остановки
stop_pidfile "bot"
stop_pidfile "backend"

# Подстраховка: добиваем по сигнатуре, если что-то осталось от прежних запусков
LEFTOVERS_BACKEND=$(pgrep -f "uvicorn main:app --host 0.0.0.0 --port 8005" || true)
LEFTOVERS_BOT=$(pgrep -f "python bot/main.py" || true)

if [ -n "$LEFTOVERS_BACKEND" ]; then
    log "[stop] backend: добиваю осиротевшие процессы: $LEFTOVERS_BACKEND"
    kill -TERM $LEFTOVERS_BACKEND 2>/dev/null || true
fi
if [ -n "$LEFTOVERS_BOT" ]; then
    log "[stop] bot: добиваю осиротевшие процессы: $LEFTOVERS_BOT"
    kill -TERM $LEFTOVERS_BOT 2>/dev/null || true
fi

log "✅ Остановлено."
