#!/bin/bash
# =============================================================================
# Log Parser Functions
# Provides log analysis functions for validation system
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../config"
ERROR_PATTERNS_FILE="$CONFIG_DIR/error_patterns.json"

# Collect logs from all containers
# Usage: collect_container_logs <container_name> [lines]
# Returns: Container logs (stdout and stderr combined)
collect_container_logs() {
    local container_name=$1
    local lines=${2:-500}
    
    if [ -z "$container_name" ]; then
        echo "Error: Container name is required" >&2
        return 1
    fi
    
    # Check if container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo "Error: Container '$container_name' not found" >&2
        return 1
    fi
    
    # Get logs from container
    docker logs --tail "$lines" "$container_name" 2>&1
}

# Collect logs from all healthcare_ai containers
# Usage: collect_all_container_logs [lines]
# Returns: Associative array of container logs (requires bash 4+)
collect_all_container_logs() {
    local lines=${1:-500}
    local containers=(
        "healthcare_ai_postgres"
        "healthcare_ai_redis"
        "healthcare_ai_backend"
        "healthcare_ai_stt"
        "healthcare_ai_motion"
        "healthcare_ai_assessment"
        "healthcare_ai_pgadmin"
    )
    
    for container in "${containers[@]}"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "=== Logs for $container ==="
            collect_container_logs "$container" "$lines"
            echo ""
        fi
    done
}

# Load error patterns from JSON config
# Usage: load_error_patterns
# Returns: Prints error patterns (one per line)
load_error_patterns() {
    if [ ! -f "$ERROR_PATTERNS_FILE" ]; then
        echo "Error: Error patterns file not found: $ERROR_PATTERNS_FILE" >&2
        return 1
    fi
    
    # Extract error patterns using grep and sed (works without jq)
    grep -o '"pattern"[[:space:]]*:[[:space:]]*"[^"]*"' "$ERROR_PATTERNS_FILE" | \
        sed 's/"pattern"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/'
}

# Load warning patterns from JSON config
# Usage: load_warning_patterns
# Returns: Prints warning patterns (one per line)
load_warning_patterns() {
    if [ ! -f "$ERROR_PATTERNS_FILE" ]; then
        echo "Error: Error patterns file not found: $ERROR_PATTERNS_FILE" >&2
        return 1
    fi
    
    # Extract warning patterns from the warning_patterns section
    sed -n '/"warning_patterns"/,/"ignore_patterns"/p' "$ERROR_PATTERNS_FILE" | \
        grep -o '"pattern"[[:space:]]*:[[:space:]]*"[^"]*"' | \
        sed 's/"pattern"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/'
}

# Load ignore patterns from JSON config
# Usage: load_ignore_patterns
# Returns: Prints ignore patterns (one per line)
load_ignore_patterns() {
    if [ ! -f "$ERROR_PATTERNS_FILE" ]; then
        echo "Error: Error patterns file not found: $ERROR_PATTERNS_FILE" >&2
        return 1
    fi
    
    # Extract ignore patterns
    sed -n '/"ignore_patterns"/,/]/p' "$ERROR_PATTERNS_FILE" | \
        grep -o '"[^"]*"' | \
        sed 's/"//g' | \
        grep -v "ignore_patterns"
}

# Scan logs for errors using pattern matching
# Usage: scan_for_errors <logs>
# Returns: Lines matching error patterns with line numbers
scan_for_errors() {
    local logs="$1"
    
    if [ -z "$logs" ]; then
        return 0
    fi
    
    # Use grep with case-insensitive matching for common error patterns
    # This matches: error, exception, traceback, failed, critical
    echo "$logs" | grep -niE "(error|exception|traceback|failed|critical)" || true
}

# Scan logs for warnings with filtering
# Usage: scan_for_warnings <logs>
# Returns: Lines matching warning patterns (excluding expected warnings)
scan_for_warnings() {
    local logs="$1"
    
    if [ -z "$logs" ]; then
        return 0
    fi
    
    # First, find all warning lines
    local warnings
    warnings=$(echo "$logs" | grep -niE "(warning|warn|deprecated)" || true)
    
    if [ -z "$warnings" ]; then
        return 0
    fi
    
    # Filter out expected warnings
    local filtered_warnings="$warnings"
    
    # Load ignore patterns and filter them out
    while IFS= read -r ignore_pattern; do
        if [ -n "$ignore_pattern" ]; then
            filtered_warnings=$(echo "$filtered_warnings" | grep -vi "$ignore_pattern" || true)
        fi
    done < <(load_ignore_patterns)
    
    echo "$filtered_warnings"
}

# Extract error context (surrounding lines)
# Usage: extract_error_context <logs> <line_number> [context_lines]
# Returns: Lines around the error (default: 2 lines before and after)
extract_error_context() {
    local logs="$1"
    local line_number=$2
    local context_lines=${3:-2}
    
    if [ -z "$logs" ] || [ -z "$line_number" ]; then
        return 1
    fi
    
    # Calculate start and end line numbers
    local start_line=$((line_number - context_lines))
    local end_line=$((line_number + context_lines))
    
    # Ensure start line is at least 1
    if [ $start_line -lt 1 ]; then
        start_line=1
    fi
    
    # Extract the context lines
    echo "$logs" | sed -n "${start_line},${end_line}p"
}

# Filter expected warnings from log output
# Usage: filter_expected_warnings <logs>
# Returns: Logs with expected warnings removed
filter_expected_warnings() {
    local logs="$1"
    
    if [ -z "$logs" ]; then
        return 0
    fi
    
    local filtered_logs="$logs"
    
    # Load ignore patterns and filter them out
    while IFS= read -r ignore_pattern; do
        if [ -n "$ignore_pattern" ]; then
            filtered_logs=$(echo "$filtered_logs" | grep -vi "$ignore_pattern" || true)
        fi
    done < <(load_ignore_patterns)
    
    echo "$filtered_logs"
}

# Count errors in logs
# Usage: count_errors <logs>
# Returns: Number of error lines found
count_errors() {
    local logs="$1"
    
    if [ -z "$logs" ]; then
        echo "0"
        return 0
    fi
    
    local error_lines
    error_lines=$(scan_for_errors "$logs")
    
    if [ -z "$error_lines" ]; then
        echo "0"
    else
        echo "$error_lines" | wc -l
    fi
}

# Count warnings in logs
# Usage: count_warnings <logs>
# Returns: Number of warning lines found (excluding expected warnings)
count_warnings() {
    local logs="$1"
    
    if [ -z "$logs" ]; then
        echo "0"
        return 0
    fi
    
    local warning_lines
    warning_lines=$(scan_for_warnings "$logs")
    
    if [ -z "$warning_lines" ]; then
        echo "0"
    else
        echo "$warning_lines" | wc -l
    fi
}

# Analyze logs for a specific container
# Usage: analyze_container_logs <container_name> [lines]
# Returns: JSON-like summary of log analysis
analyze_container_logs() {
    local container_name=$1
    local lines=${2:-500}
    
    echo "Analyzing logs for $container_name..."
    
    # Collect logs
    local logs
    logs=$(collect_container_logs "$container_name" "$lines" 2>&1)
    
    if [ $? -ne 0 ]; then
        echo "  Status: Failed to collect logs"
        return 1
    fi
    
    # Count errors and warnings
    local error_count
    local warning_count
    error_count=$(count_errors "$logs")
    warning_count=$(count_warnings "$logs")
    
    echo "  Total lines: $(echo "$logs" | wc -l)"
    echo "  Errors found: $error_count"
    echo "  Warnings found: $warning_count"
    
    # Show first few errors if any
    if [ "$error_count" -gt 0 ]; then
        echo "  Sample errors:"
        scan_for_errors "$logs" | head -n 3 | sed 's/^/    /'
    fi
    
    # Show first few warnings if any
    if [ "$warning_count" -gt 0 ]; then
        echo "  Sample warnings:"
        scan_for_warnings "$logs" | head -n 3 | sed 's/^/    /'
    fi
    
    return 0
}

# Analyze logs for all containers
# Usage: analyze_all_container_logs [lines]
# Returns: Summary of log analysis for all containers
analyze_all_container_logs() {
    local lines=${1:-500}
    local containers=(
        "healthcare_ai_postgres"
        "healthcare_ai_redis"
        "healthcare_ai_backend"
        "healthcare_ai_stt"
        "healthcare_ai_motion"
        "healthcare_ai_assessment"
        "healthcare_ai_pgadmin"
    )
    
    echo "=== Log Analysis Summary ==="
    echo ""
    
    local total_errors=0
    local total_warnings=0
    
    for container in "${containers[@]}"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            analyze_container_logs "$container" "$lines"
            
            # Collect logs and count
            local logs
            logs=$(collect_container_logs "$container" "$lines" 2>/dev/null)
            if [ $? -eq 0 ]; then
                local errors=$(count_errors "$logs")
                local warnings=$(count_warnings "$logs")
                total_errors=$((total_errors + errors))
                total_warnings=$((total_warnings + warnings))
            fi
            
            echo ""
        fi
    done
    
    echo "=== Overall Summary ==="
    echo "  Total errors across all containers: $total_errors"
    echo "  Total warnings across all containers: $total_warnings"
    
    if [ $total_errors -eq 0 ] && [ $total_warnings -eq 0 ]; then
        echo "  Status: ✓ No critical issues found"
        return 0
    elif [ $total_errors -gt 0 ]; then
        echo "  Status: ✗ Critical errors found"
        return 1
    else
        echo "  Status: ⚠ Warnings found (non-critical)"
        return 0
    fi
}

# Scan for specific error pattern
# Usage: scan_for_pattern <logs> <pattern>
# Returns: Lines matching the specific pattern
scan_for_pattern() {
    local logs="$1"
    local pattern="$2"
    
    if [ -z "$logs" ] || [ -z "$pattern" ]; then
        return 0
    fi
    
    echo "$logs" | grep -niE "$pattern" || true
}

# Check for database connection errors
# Usage: check_database_errors <logs>
# Returns: Lines with database connection errors
check_database_errors() {
    local logs="$1"
    
    scan_for_pattern "$logs" "(connection refused|could not connect|connection timeout).*postgres"
}

# Check for port binding errors
# Usage: check_port_errors <logs>
# Returns: Lines with port binding errors
check_port_errors() {
    local logs="$1"
    
    scan_for_pattern "$logs" "(port.*already in use|address already in use)"
}

# Check for permission errors
# Usage: check_permission_errors <logs>
# Returns: Lines with permission errors
check_permission_errors() {
    local logs="$1"
    
    scan_for_pattern "$logs" "(permission denied|access denied)"
}

# Check for memory errors
# Usage: check_memory_errors <logs>
# Returns: Lines with memory errors
check_memory_errors() {
    local logs="$1"
    
    scan_for_pattern "$logs" "(out of memory|memory allocation failed)"
}

# Generate log analysis report
# Usage: generate_log_report [lines] [output_file]
# Returns: Detailed log analysis report
generate_log_report() {
    local lines=${1:-500}
    local output_file=${2:-}
    
    local report
    report=$(analyze_all_container_logs "$lines")
    
    if [ -n "$output_file" ]; then
        echo "$report" > "$output_file"
        echo "Log analysis report saved to: $output_file"
    else
        echo "$report"
    fi
}
