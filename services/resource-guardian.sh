#!/bin/bash
# VM Resource Guardian v1.0
# Автоматический контроль ресурсов Oracle VM с интеллектуальным управлением

# Конфигурация
MEMORY_THRESHOLD=85       # Порог памяти в %
CRITICAL_THRESHOLD=90      # Критический порог
CHECK_INTERVAL=30         # Интервал проверки в секундах
LOG_FILE="/home/ubuntu/resource-guardian.log"
RESTART_THRESHOLD=100     # Порог перезапусков для перезапуска сервиса

# Цвета для вывода
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Приоритеты сервисов (1=критический, 2=важный, 3=второстепенный)
declare -A SERVICE_PRIORITY
SERVICE_PRIORITY["oracle-dashboard"]=3
SERVICE_PRIORITY["claude-cli"]=2
SERVICE_PRIORITY["claude-code-tunnel"]=1
SERVICE_PRIORITY["claude-connect"]=1
SERVICE_PRIORITY["control-center"]=2
SERVICE_PRIORITY["https-bridges"]=2
SERVICE_PRIORITY["https-monitor"]=3
SERVICE_PRIORITY["mcp-bridge-v2"]=1
SERVICE_PRIORITY["mcp-tunnel"]=2
SERVICE_PRIORITY["mcp-web-tunnel"]=2
SERVICE_PRIORITY["tunnel-manager"]=3
SERVICE_PRIORITY["visaginas360-bot"]=3
SERVICE_PRIORITY["vm-mcp-full"]=3
SERVICE_PRIORITY["web-port-4000"]=2
SERVICE_PRIORITY["websocket-bridge"]=3

# Функция логирования
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Получить текущее использование памяти
get_memory_usage() {
    free | grep Mem | awk '{print int($3/$2 * 100)}'
}

# Получить информацию о PM2 процессах
get_pm2_info() {
    pm2 jlist 2>/dev/null
}

# Остановить второстепенные сервисы
stop_low_priority_services() {
    local memory_usage=$1
    log_message "⚠️ Память: ${memory_usage}% - останавливаю второстепенные сервисы"
    
    # Останавливаем сервисы с приоритетом 3
    for service in "${!SERVICE_PRIORITY[@]}"; do
        if [[ ${SERVICE_PRIORITY[$service]} -eq 3 ]]; then
            pm2 stop "$service" 2>/dev/null && \
                log_message "  ↓ Остановлен: $service (приоритет 3)"
        fi
    done
}

# Остановить важные сервисы
stop_medium_priority_services() {
    local memory_usage=$1
    log_message "🔴 КРИТИЧНО! Память: ${memory_usage}% - останавливаю важные сервисы"
    
    # Останавливаем сервисы с приоритетом 2
    for service in "${!SERVICE_PRIORITY[@]}"; do
        if [[ ${SERVICE_PRIORITY[$service]} -eq 2 ]]; then
            pm2 stop "$service" 2>/dev/null && \
                log_message "  ↓ Остановлен: $service (приоритет 2)"
        fi
    done
}

# Перезапустить сервисы с большим количеством рестартов
fix_unstable_services() {
    local json_output=$(pm2 jlist 2>/dev/null)
    if [[ -z "$json_output" ]]; then
        return
    fi
    
    # Используем python для парсинга JSON
    python3 - <<EOF
import json
import subprocess
import sys

try:
    data = json.loads('''${json_output}''')
    for app in data:
        if app.get('pm2_env', {}).get('restart_time', 0) > ${RESTART_THRESHOLD}:
            name = app.get('name', 'unknown')
            restarts = app['pm2_env']['restart_time']
            print(f"Fixing {name} with {restarts} restarts")
            subprocess.run(['pm2', 'delete', name], capture_output=True)
            subprocess.run(['pm2', 'start', f'/home/ubuntu/{name}.js', '--name', name], capture_output=True)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
EOF
}

# Восстановить критические сервисы если память позволяет
restore_critical_services() {
    local memory_usage=$1
    
    if [[ $memory_usage -lt 70 ]]; then
        log_message "✅ Память: ${memory_usage}% - восстанавливаю критические сервисы"
        
        # Проверяем и запускаем критические сервисы
        for service in "${!SERVICE_PRIORITY[@]}"; do
            if [[ ${SERVICE_PRIORITY[$service]} -eq 1 ]]; then
                status=$(pm2 info "$service" 2>/dev/null | grep "status" | awk '{print $4}')
                if [[ "$status" == "stopped" ]] || [[ -z "$status" ]]; then
                    pm2 start "$service" 2>/dev/null && \
                        log_message "  ↑ Запущен: $service (критический)"
                fi
            fi
        done
    fi
}

# Очистка кэша и буферов
clear_system_cache() {
    log_message "🧹 Очистка системного кэша"
    sync
    echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1
    
    # Очистка логов PM2
    pm2 flush > /dev/null 2>&1
    
    # Очистка старых логов
    find /home/ubuntu/.pm2/logs -type f -name "*.log" -mtime +7 -delete 2>/dev/null
}

# Мониторинг системы
monitor_system() {
    echo -e "${GREEN}=== VM Resource Guardian ====${NC}"
    echo -e "Память (порог): ${MEMORY_THRESHOLD}%"
    echo -e "Критический порог: ${CRITICAL_THRESHOLD}%"
    echo -e "Интервал проверки: ${CHECK_INTERVAL}с"
    echo -e "${GREEN}============================${NC}\n"
    
    local last_cleanup=0
    local current_time
    
    while true; do
        current_time=$(date +%s)
        memory_usage=$(get_memory_usage)
        
        # Цветовая индикация
        if [[ $memory_usage -lt 70 ]]; then
            color=$GREEN
            status="✅ Норма"
        elif [[ $memory_usage -lt $MEMORY_THRESHOLD ]]; then
            color=$YELLOW
            status="⚠️ Внимание"
        else
            color=$RED
            status="🔴 Критично"
        fi
        
        echo -e "${color}[$(date '+%H:%M:%S')] Память: ${memory_usage}% - ${status}${NC}"
        
        # Проверка и действия
        if [[ $memory_usage -gt $CRITICAL_THRESHOLD ]]; then
            stop_medium_priority_services $memory_usage
            clear_system_cache
        elif [[ $memory_usage -gt $MEMORY_THRESHOLD ]]; then
            stop_low_priority_services $memory_usage
        else
            restore_critical_services $memory_usage
        fi
        
        # Исправление нестабильных сервисов каждые 5 минут
        if [[ $((current_time - last_cleanup)) -gt 300 ]]; then
            fix_unstable_services
            last_cleanup=$current_time
        fi
        
        sleep $CHECK_INTERVAL
    done
}

# Команды управления
case "$1" in
    start)
        log_message "🚀 Запуск Resource Guardian"
        monitor_system
        ;;
    
    daemon)
        log_message "👾 Запуск Resource Guardian в фоне"
        nohup $0 start > /dev/null 2>&1 &
        echo $! > /home/ubuntu/resource-guardian.pid
        echo "Guardian запущен с PID: $(cat /home/ubuntu/resource-guardian.pid)"
        ;;
    
    stop)
        if [[ -f /home/ubuntu/resource-guardian.pid ]]; then
            kill $(cat /home/ubuntu/resource-guardian.pid) 2>/dev/null
            rm /home/ubuntu/resource-guardian.pid
            log_message "⏹️ Resource Guardian остановлен"
        else
            echo "Guardian не запущен"
        fi
        ;;
    
    status)
        if [[ -f /home/ubuntu/resource-guardian.pid ]] && ps -p $(cat /home/ubuntu/resource-guardian.pid) > /dev/null 2>&1; then
            echo "✅ Guardian работает (PID: $(cat /home/ubuntu/resource-guardian.pid))"
            echo "📊 Текущая память: $(get_memory_usage)%"
            tail -n 10 "$LOG_FILE"
        else
            echo "❌ Guardian не запущен"
        fi
        ;;
    
    fix)
        echo "🔧 Исправление нестабильных сервисов..."
        fix_unstable_services
        echo "✅ Готово"
        ;;
    
    clean)
        echo "🧹 Очистка системы..."
        clear_system_cache
        echo "✅ Готово"
        ;;
    
    *)
        echo "Использование: $0 {start|daemon|stop|status|fix|clean}"
        echo ""
        echo "  start  - Запустить в интерактивном режиме"
        echo "  daemon - Запустить в фоне"
        echo "  stop   - Остановить Guardian"
        echo "  status - Проверить статус"
        echo "  fix    - Исправить нестабильные сервисы"
        echo "  clean  - Очистить кэш системы"
        exit 1
        ;;
esac
