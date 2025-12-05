#!/bin/bash

# Talk2Me UI Monitoring Script
# This script provides basic monitoring and health checks

set -e

# Configuration
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/health}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
LOG_FILE="${LOG_FILE:-logs/monitor.log}"
METRICS_FILE="${METRICS_FILE:-logs/metrics.json}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure log directory exists
mkdir -p logs

# Logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    echo "[$timestamp] [$level] $message"
}

# Health check function
check_health() {
    local response
    local http_code

    # Make health check request
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$HEALTH_URL" 2>/dev/null)
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')

    if [ "$http_code" -eq 200 ]; then
        log "INFO" "Health check passed (HTTP $http_code)"
        return 0
    else
        log "ERROR" "Health check failed (HTTP $http_code)"
        return 1
    fi
}

# Collect system metrics
collect_metrics() {
    local timestamp=$(date '+%s')
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    local mem_usage=$(free | grep Mem | awk '{printf "%.2f", $3/$2 * 100.0}')
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

    # Create metrics JSON
    cat > "$METRICS_FILE" << EOF
{
  "timestamp": $timestamp,
  "cpu_percent": $cpu_usage,
  "memory_percent": $mem_usage,
  "disk_percent": $disk_usage,
  "health_status": "$(check_health && echo "healthy" || echo "unhealthy")"
}
EOF

    log "INFO" "Metrics collected - CPU: ${cpu_usage}%, Memory: ${mem_usage}%, Disk: ${disk_usage}%"
}

# Display status
show_status() {
    echo "Talk2Me UI Monitoring Status"
    echo "============================"

    # Check if service is running
    if curl -s "$HEALTH_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is running${NC}"
    else
        echo -e "${RED}✗ Service is not responding${NC}"
    fi

    # Show recent logs
    echo ""
    echo "Recent Logs:"
    echo "------------"
    tail -10 "$LOG_FILE" 2>/dev/null || echo "No logs available"

    # Show current metrics
    echo ""
    echo "Current Metrics:"
    echo "----------------"
    if [ -f "$METRICS_FILE" ]; then
        cat "$METRICS_FILE" | python3 -m json.tool 2>/dev/null || cat "$METRICS_FILE"
    else
        echo "No metrics available"
    fi
}

# Main monitoring loop
monitor_loop() {
    log "INFO" "Starting monitoring loop (interval: ${CHECK_INTERVAL}s)"

    while true; do
        check_health
        collect_metrics
        sleep "$CHECK_INTERVAL"
    done
}

# Parse command line arguments
case "${1:-}" in
    "status")
        show_status
        ;;
    "check")
        if check_health; then
            echo -e "${GREEN}✓ Health check passed${NC}"
            exit 0
        else
            echo -e "${RED}✗ Health check failed${NC}"
            exit 1
        fi
        ;;
    "metrics")
        collect_metrics
        echo "Metrics collected. View with: cat $METRICS_FILE"
        ;;
    "loop")
        monitor_loop
        ;;
    *)
        echo "Usage: $0 {status|check|metrics|loop}"
        echo ""
        echo "Commands:"
        echo "  status   - Show current service status and metrics"
        echo "  check    - Perform a single health check"
        echo "  metrics  - Collect and display current metrics"
        echo "  loop     - Start continuous monitoring loop"
        echo ""
        echo "Environment variables:"
        echo "  HEALTH_URL      - Health check endpoint URL (default: http://localhost:8000/api/health)"
        echo "  CHECK_INTERVAL  - Monitoring interval in seconds (default: 30)"
        echo "  LOG_FILE        - Log file path (default: logs/monitor.log)"
        echo "  METRICS_FILE    - Metrics file path (default: logs/metrics.json)"
        exit 1
        ;;
esac
