#!/bin/bash
# =============================================================================
# Reporter Functions
# Provides report generation and console output functions for validation system
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTS_DIR="$SCRIPT_DIR/../../reports"

# Color codes for console output
COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_CYAN='\033[0;36m'
COLOR_RESET='\033[0m'

# Unicode symbols for status indicators
SYMBOL_SUCCESS="✓"
SYMBOL_ERROR="✗"
SYMBOL_WARNING="⚠"
SYMBOL_INFO="ℹ"
SYMBOL_PROGRESS="→"

# Initialize validation results storage
declare -A VALIDATION_RESULTS
declare -a VALIDATION_PHASES
declare -a VALIDATION_ERRORS
declare -a VALIDATION_WARNINGS
VALIDATION_START_TIME=""
VALIDATION_END_TIME=""
VALIDATION_OVERALL_STATUS="passed"

# =============================================================================
# Console Output Functions
# =============================================================================

# Print success message with green color
# Usage: console_success <message>
console_success() {
    local message="$1"
    echo -e "${COLOR_GREEN}${SYMBOL_SUCCESS}${COLOR_RESET} ${message}"
}

# Print error message with red color
# Usage: console_error <message>
console_error() {
    local message="$1"
    echo -e "${COLOR_RED}${SYMBOL_ERROR}${COLOR_RESET} ${message}"
}

# Print warning message with yellow color
# Usage: console_warning <message>
console_warning() {
    local message="$1"
    echo -e "${COLOR_YELLOW}${SYMBOL_WARNING}${COLOR_RESET} ${message}"
}

# Print info message with cyan color
# Usage: console_info <message>
console_info() {
    local message="$1"
    echo -e "${COLOR_CYAN}${SYMBOL_INFO}${COLOR_RESET} ${message}"
}

# Print progress message with blue color
# Usage: console_progress <message>
console_progress() {
    local message="$1"
    echo -e "${COLOR_BLUE}${SYMBOL_PROGRESS}${COLOR_RESET} ${message}"
}

# Print phase header
# Usage: console_phase_header <phase_name>
console_phase_header() {
    local phase_name="$1"
    echo ""
    echo -e "${COLOR_CYAN}═══════════════════════════════════════════════════════════════${COLOR_RESET}"
    echo -e "${COLOR_CYAN}  ${phase_name}${COLOR_RESET}"
    echo -e "${COLOR_CYAN}═══════════════════════════════════════════════════════════════${COLOR_RESET}"
}

# Print section header
# Usage: console_section_header <section_name>
console_section_header() {
    local section_name="$1"
    echo ""
    echo -e "${COLOR_BLUE}───────────────────────────────────────────────────────────────${COLOR_RESET}"
    echo -e "${COLOR_BLUE}  ${section_name}${COLOR_RESET}"
    echo -e "${COLOR_BLUE}───────────────────────────────────────────────────────────────${COLOR_RESET}"
}

# Print phase status with appropriate color
# Usage: console_phase_status <phase_name> <status> [duration_seconds]
console_phase_status() {
    local phase_name="$1"
    local status="$2"
    local duration="${3:-}"
    
    local status_text=""
    local duration_text=""
    
    if [ -n "$duration" ]; then
        duration_text=" (${duration}s)"
    fi
    
    case "$status" in
        "passed"|"success")
            status_text="${COLOR_GREEN}${SYMBOL_SUCCESS} PASSED${COLOR_RESET}"
            ;;
        "failed"|"error")
            status_text="${COLOR_RED}${SYMBOL_ERROR} FAILED${COLOR_RESET}"
            ;;
        "warning")
            status_text="${COLOR_YELLOW}${SYMBOL_WARNING} WARNING${COLOR_RESET}"
            ;;
        "skipped")
            status_text="${COLOR_CYAN}⊘ SKIPPED${COLOR_RESET}"
            ;;
        "in_progress")
            status_text="${COLOR_BLUE}${SYMBOL_PROGRESS} IN PROGRESS${COLOR_RESET}"
            ;;
        *)
            status_text="${status}"
            ;;
    esac
    
    echo -e "${phase_name}... ${status_text}${duration_text}"
}

# =============================================================================
# Progress Indicator Functions
# =============================================================================

# Show progress bar
# Usage: show_progress_bar <current> <total> [width]
show_progress_bar() {
    local current=$1
    local total=$2
    local width=${3:-50}
    
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    
    printf "\r["
    printf "%${filled}s" | tr ' ' '='
    printf "%${empty}s" | tr ' ' ' '
    printf "] %3d%%" "$percentage"
}

# Show spinner animation
# Usage: show_spinner <message>
# Note: Call stop_spinner to stop the animation
show_spinner() {
    local message="$1"
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    
    while true; do
        i=$(( (i+1) % 10 ))
        printf "\r${COLOR_BLUE}${spin:$i:1}${COLOR_RESET} %s" "$message"
        sleep 0.1
    done
}

# Display phase progress
# Usage: display_phase_progress <phase_number> <total_phases> <phase_name>
display_phase_progress() {
    local phase_number=$1
    local total_phases=$2
    local phase_name="$3"
    
    echo ""
    echo -e "${COLOR_CYAN}[Phase ${phase_number}/${total_phases}]${COLOR_RESET} ${phase_name}"
    show_progress_bar "$phase_number" "$total_phases" 40
    echo ""
}

# =============================================================================
# Validation Results Storage Functions
# =============================================================================

# Initialize validation tracking
# Usage: init_validation_tracking
init_validation_tracking() {
    VALIDATION_START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    VALIDATION_PHASES=()
    VALIDATION_ERRORS=()
    VALIDATION_WARNINGS=()
    VALIDATION_OVERALL_STATUS="passed"
    
    # Create reports directory if it doesn't exist
    mkdir -p "$REPORTS_DIR"
}

# Record phase result
# Usage: record_phase_result <phase_name> <status> <duration_seconds> <details>
record_phase_result() {
    local phase_name="$1"
    local status="$2"
    local duration="$3"
    local details="$4"
    
    # Store phase result
    VALIDATION_RESULTS["${phase_name}_status"]="$status"
    VALIDATION_RESULTS["${phase_name}_duration"]="$duration"
    VALIDATION_RESULTS["${phase_name}_details"]="$details"
    
    # Add to phases list if not already present
    if [[ ! " ${VALIDATION_PHASES[@]} " =~ " ${phase_name} " ]]; then
        VALIDATION_PHASES+=("$phase_name")
    fi
    
    # Update overall status
    if [ "$status" = "failed" ] || [ "$status" = "error" ]; then
        VALIDATION_OVERALL_STATUS="failed"
    elif [ "$status" = "warning" ] && [ "$VALIDATION_OVERALL_STATUS" != "failed" ]; then
        VALIDATION_OVERALL_STATUS="warning"
    fi
}

# Record error
# Usage: record_error <phase> <severity> <message> <details> <recommendation>
record_error() {
    local phase="$1"
    local severity="$2"
    local message="$3"
    local details="$4"
    local recommendation="$5"
    
    local error_entry="PHASE:${phase}|SEVERITY:${severity}|MESSAGE:${message}|DETAILS:${details}|RECOMMENDATION:${recommendation}"
    VALIDATION_ERRORS+=("$error_entry")
}

# Record warning
# Usage: record_warning <phase> <message> <details> <recommendation>
record_warning() {
    local phase="$1"
    local message="$2"
    local details="$3"
    local recommendation="$4"
    
    local warning_entry="PHASE:${phase}|MESSAGE:${message}|DETAILS:${details}|RECOMMENDATION:${recommendation}"
    VALIDATION_WARNINGS+=("$warning_entry")
}

# Finalize validation tracking
# Usage: finalize_validation_tracking
finalize_validation_tracking() {
    VALIDATION_END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
}

# =============================================================================
# JSON Report Generation
# =============================================================================

# Escape JSON string
# Usage: json_escape <string>
json_escape() {
    local string="$1"
    # Escape backslashes, quotes, newlines, tabs
    echo "$string" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\n/\\n/g; s/\t/\\t/g'
}

# Generate JSON report with complete validation results
# Usage: generate_json_report [output_file]
# Returns: JSON formatted validation report
generate_json_report() {
    local output_file="${1:-}"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local validation_id=$(date +%s)
    
    # Calculate duration
    local duration_seconds=0
    if [ -n "$VALIDATION_START_TIME" ] && [ -n "$VALIDATION_END_TIME" ]; then
        local start_epoch=$(date -d "$VALIDATION_START_TIME" +%s 2>/dev/null || echo "0")
        local end_epoch=$(date -d "$VALIDATION_END_TIME" +%s 2>/dev/null || echo "0")
        duration_seconds=$((end_epoch - start_epoch))
    fi
    
    # Get system information
    local os_type=$(uname -s)
    local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo "unknown")
    local compose_version=$(docker-compose --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo "unknown")
    
    # Start building JSON
    local json="{"
    json="${json}\"validation_id\":\"${validation_id}\","
    json="${json}\"timestamp\":\"${timestamp}\","
    json="${json}\"duration_seconds\":${duration_seconds},"
    json="${json}\"overall_status\":\"${VALIDATION_OVERALL_STATUS}\","
    
    # Environment section
    json="${json}\"environment\":{"
    json="${json}\"os\":\"${os_type}\","
    json="${json}\"docker_version\":\"${docker_version}\","
    json="${json}\"docker_compose_version\":\"${compose_version}\""
    json="${json}},"
    
    # Phases section
    json="${json}\"phases\":["
    local first_phase=true
    for phase in "${VALIDATION_PHASES[@]}"; do
        if [ "$first_phase" = false ]; then
            json="${json},"
        fi
        first_phase=false
        
        local status="${VALIDATION_RESULTS[${phase}_status]:-unknown}"
        local duration="${VALIDATION_RESULTS[${phase}_duration]:-0}"
        local details="${VALIDATION_RESULTS[${phase}_details]:-}"
        
        json="${json}{\"name\":\"${phase}\","
        json="${json}\"status\":\"${status}\","
        json="${json}\"duration_seconds\":${duration},"
        json="${json}\"details\":\"$(json_escape "$details")\"}"
    done
    json="${json}],"
    
    # Errors section
    json="${json}\"errors\":["
    local first_error=true
    for error in "${VALIDATION_ERRORS[@]}"; do
        if [ "$first_error" = false ]; then
            json="${json},"
        fi
        first_error=false
        
        # Parse error entry
        local phase=$(echo "$error" | sed -n 's/.*PHASE:\([^|]*\).*/\1/p')
        local severity=$(echo "$error" | sed -n 's/.*SEVERITY:\([^|]*\).*/\1/p')
        local message=$(echo "$error" | sed -n 's/.*MESSAGE:\([^|]*\).*/\1/p')
        local details=$(echo "$error" | sed -n 's/.*DETAILS:\([^|]*\).*/\1/p')
        local recommendation=$(echo "$error" | sed -n 's/.*RECOMMENDATION:\([^|]*\).*/\1/p')
        
        json="${json}{\"phase\":\"${phase}\","
        json="${json}\"severity\":\"${severity}\","
        json="${json}\"message\":\"$(json_escape "$message")\","
        json="${json}\"details\":\"$(json_escape "$details")\","
        json="${json}\"recommendation\":\"$(json_escape "$recommendation")\"}"
    done
    json="${json}],"
    
    # Warnings section
    json="${json}\"warnings\":["
    local first_warning=true
    for warning in "${VALIDATION_WARNINGS[@]}"; do
        if [ "$first_warning" = false ]; then
            json="${json},"
        fi
        first_warning=false
        
        # Parse warning entry
        local phase=$(echo "$warning" | sed -n 's/.*PHASE:\([^|]*\).*/\1/p')
        local message=$(echo "$warning" | sed -n 's/.*MESSAGE:\([^|]*\).*/\1/p')
        local details=$(echo "$warning" | sed -n 's/.*DETAILS:\([^|]*\).*/\1/p')
        local recommendation=$(echo "$warning" | sed -n 's/.*RECOMMENDATION:\([^|]*\).*/\1/p')
        
        json="${json}{\"phase\":\"${phase}\","
        json="${json}\"message\":\"$(json_escape "$message")\","
        json="${json}\"details\":\"$(json_escape "$details")\","
        json="${json}\"recommendation\":\"$(json_escape "$recommendation")\"}"
    done
    json="${json}],"
    
    # Recommendations section
    json="${json}\"recommendations\":["
    if [ "$VALIDATION_OVERALL_STATUS" = "passed" ]; then
        json="${json}\"All validation tests passed. Ready for GitHub upload.\""
    elif [ "$VALIDATION_OVERALL_STATUS" = "warning" ]; then
        json="${json}\"Validation completed with warnings. Review warnings before deployment.\""
    else
        json="${json}\"Validation failed. Review errors and fix issues before deployment.\""
    fi
    json="${json}],"
    
    # Deployment readiness
    local ready_for_deployment="false"
    if [ "$VALIDATION_OVERALL_STATUS" = "passed" ]; then
        ready_for_deployment="true"
    fi
    json="${json}\"ready_for_deployment\":${ready_for_deployment}"
    
    json="${json}}"
    
    # Output to file or stdout
    if [ -n "$output_file" ]; then
        echo "$json" > "$output_file"
        console_success "JSON report saved to: $output_file"
    else
        echo "$json"
    fi
}

# =============================================================================
# Text Report Generation
# =============================================================================

# Generate human-readable text report
# Usage: generate_text_report [output_file]
# Returns: Human-readable validation report
generate_text_report() {
    local output_file="${1:-}"
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    
    # Calculate duration
    local duration_seconds=0
    local duration_text="0s"
    if [ -n "$VALIDATION_START_TIME" ] && [ -n "$VALIDATION_END_TIME" ]; then
        local start_epoch=$(date -d "$VALIDATION_START_TIME" +%s 2>/dev/null || echo "0")
        local end_epoch=$(date -d "$VALIDATION_END_TIME" +%s 2>/dev/null || echo "0")
        duration_seconds=$((end_epoch - start_epoch))
        
        local minutes=$((duration_seconds / 60))
        local seconds=$((duration_seconds % 60))
        if [ $minutes -gt 0 ]; then
            duration_text="${minutes}m ${seconds}s"
        else
            duration_text="${seconds}s"
        fi
    fi
    
    # Get system information
    local os_type=$(uname -s)
    local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo "unknown")
    local compose_version=$(docker-compose --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo "unknown")
    
    # Build report
    local report=""
    report="${report}═══════════════════════════════════════════════════════════════\n"
    report="${report}  DOCKER PRE-DEPLOYMENT VALIDATION REPORT\n"
    report="${report}═══════════════════════════════════════════════════════════════\n"
    report="${report}\n"
    
    # Summary section
    report="${report}SUMMARY\n"
    report="${report}───────────────────────────────────────────────────────────────\n"
    report="${report}Timestamp:        ${timestamp}\n"
    report="${report}Duration:         ${duration_text}\n"
    report="${report}Overall Status:   ${VALIDATION_OVERALL_STATUS^^}\n"
    report="${report}Operating System: ${os_type}\n"
    report="${report}Docker Version:   ${docker_version}\n"
    report="${report}Compose Version:  ${compose_version}\n"
    report="${report}\n"
    
    # Phases section
    report="${report}VALIDATION PHASES\n"
    report="${report}───────────────────────────────────────────────────────────────\n"
    for phase in "${VALIDATION_PHASES[@]}"; do
        local status="${VALIDATION_RESULTS[${phase}_status]:-unknown}"
        local duration="${VALIDATION_RESULTS[${phase}_duration]:-0}"
        local status_symbol=""
        
        case "$status" in
            "passed"|"success") status_symbol="✓" ;;
            "failed"|"error") status_symbol="✗" ;;
            "warning") status_symbol="⚠" ;;
            "skipped") status_symbol="⊘" ;;
            *) status_symbol="?" ;;
        esac
        
        report="${report}${status_symbol} ${phase}: ${status^^} (${duration}s)\n"
    done
    report="${report}\n"
    
    # Errors section
    if [ ${#VALIDATION_ERRORS[@]} -gt 0 ]; then
        report="${report}ERRORS (${#VALIDATION_ERRORS[@]})\n"
        report="${report}───────────────────────────────────────────────────────────────\n"
        local error_num=1
        for error in "${VALIDATION_ERRORS[@]}"; do
            local phase=$(echo "$error" | sed -n 's/.*PHASE:\([^|]*\).*/\1/p')
            local severity=$(echo "$error" | sed -n 's/.*SEVERITY:\([^|]*\).*/\1/p')
            local message=$(echo "$error" | sed -n 's/.*MESSAGE:\([^|]*\).*/\1/p')
            local details=$(echo "$error" | sed -n 's/.*DETAILS:\([^|]*\).*/\1/p')
            local recommendation=$(echo "$error" | sed -n 's/.*RECOMMENDATION:\([^|]*\).*/\1/p')
            
            report="${report}${error_num}. [${phase}] ${message}\n"
            if [ -n "$details" ]; then
                report="${report}   Details: ${details}\n"
            fi
            if [ -n "$recommendation" ]; then
                report="${report}   Fix: ${recommendation}\n"
            fi
            report="${report}\n"
            error_num=$((error_num + 1))
        done
    fi
    
    # Warnings section
    if [ ${#VALIDATION_WARNINGS[@]} -gt 0 ]; then
        report="${report}WARNINGS (${#VALIDATION_WARNINGS[@]})\n"
        report="${report}───────────────────────────────────────────────────────────────\n"
        local warning_num=1
        for warning in "${VALIDATION_WARNINGS[@]}"; do
            local phase=$(echo "$warning" | sed -n 's/.*PHASE:\([^|]*\).*/\1/p')
            local message=$(echo "$warning" | sed -n 's/.*MESSAGE:\([^|]*\).*/\1/p')
            local details=$(echo "$warning" | sed -n 's/.*DETAILS:\([^|]*\).*/\1/p')
            local recommendation=$(echo "$warning" | sed -n 's/.*RECOMMENDATION:\([^|]*\).*/\1/p')
            
            report="${report}${warning_num}. [${phase}] ${message}\n"
            if [ -n "$details" ]; then
                report="${report}   Details: ${details}\n"
            fi
            if [ -n "$recommendation" ]; then
                report="${report}   Note: ${recommendation}\n"
            fi
            report="${report}\n"
            warning_num=$((warning_num + 1))
        done
    fi
    
    # Recommendations section
    report="${report}RECOMMENDATIONS\n"
    report="${report}───────────────────────────────────────────────────────────────\n"
    if [ "$VALIDATION_OVERALL_STATUS" = "passed" ]; then
        report="${report}✓ All validation tests passed.\n"
        report="${report}✓ Docker environment is ready for deployment.\n"
        report="${report}✓ Ready for GitHub upload.\n"
    elif [ "$VALIDATION_OVERALL_STATUS" = "warning" ]; then
        report="${report}⚠ Validation completed with warnings.\n"
        report="${report}⚠ Review warnings above before deployment.\n"
        report="${report}⚠ Consider fixing warnings for production deployment.\n"
    else
        report="${report}✗ Validation failed with errors.\n"
        report="${report}✗ Fix all errors before deployment.\n"
        report="${report}✗ Review error details and recommendations above.\n"
    fi
    report="${report}\n"
    
    report="${report}═══════════════════════════════════════════════════════════════\n"
    
    # Output to file or stdout
    if [ -n "$output_file" ]; then
        echo -e "$report" > "$output_file"
        console_success "Text report saved to: $output_file"
    else
        echo -e "$report"
    fi
}

# =============================================================================
# Summary Display Functions
# =============================================================================

# Display validation summary
# Usage: display_validation_summary
display_validation_summary() {
    echo ""
    console_section_header "VALIDATION SUMMARY"
    
    # Calculate duration
    local duration_text="0s"
    if [ -n "$VALIDATION_START_TIME" ] && [ -n "$VALIDATION_END_TIME" ]; then
        local start_epoch=$(date -d "$VALIDATION_START_TIME" +%s 2>/dev/null || echo "0")
        local end_epoch=$(date -d "$VALIDATION_END_TIME" +%s 2>/dev/null || echo "0")
        local duration_seconds=$((end_epoch - start_epoch))
        
        local minutes=$((duration_seconds / 60))
        local seconds=$((duration_seconds % 60))
        if [ $minutes -gt 0 ]; then
            duration_text="${minutes}m ${seconds}s"
        else
            duration_text="${seconds}s"
        fi
    fi
    
    echo ""
    echo "Duration: ${duration_text}"
    echo "Phases Executed: ${#VALIDATION_PHASES[@]}"
    echo "Errors: ${#VALIDATION_ERRORS[@]}"
    echo "Warnings: ${#VALIDATION_WARNINGS[@]}"
    echo ""
    
    # Display overall status
    case "$VALIDATION_OVERALL_STATUS" in
        "passed")
            console_success "Overall Status: PASSED"
            console_success "Docker environment is ready for deployment!"
            ;;
        "warning")
            console_warning "Overall Status: PASSED WITH WARNINGS"
            console_warning "Review warnings before deployment"
            ;;
        "failed")
            console_error "Overall Status: FAILED"
            console_error "Fix errors before deployment"
            ;;
    esac
    
    echo ""
}

# Display phase results table
# Usage: display_phase_results
display_phase_results() {
    echo ""
    console_section_header "PHASE RESULTS"
    echo ""
    
    printf "%-30s %-15s %-10s\n" "Phase" "Status" "Duration"
    printf "%-30s %-15s %-10s\n" "------------------------------" "---------------" "----------"
    
    for phase in "${VALIDATION_PHASES[@]}"; do
        local status="${VALIDATION_RESULTS[${phase}_status]:-unknown}"
        local duration="${VALIDATION_RESULTS[${phase}_duration]:-0}"
        
        local status_display=""
        case "$status" in
            "passed"|"success")
                status_display="${COLOR_GREEN}PASSED${COLOR_RESET}"
                ;;
            "failed"|"error")
                status_display="${COLOR_RED}FAILED${COLOR_RESET}"
                ;;
            "warning")
                status_display="${COLOR_YELLOW}WARNING${COLOR_RESET}"
                ;;
            "skipped")
                status_display="${COLOR_CYAN}SKIPPED${COLOR_RESET}"
                ;;
            *)
                status_display="${status}"
                ;;
        esac
        
        printf "%-30s %-24s %-10s\n" "$phase" "$status_display" "${duration}s"
    done
    
    echo ""
}

# =============================================================================
# Report Generation Wrapper
# =============================================================================

# Generate all reports (JSON and text)
# Usage: generate_all_reports
generate_all_reports() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local json_file="$REPORTS_DIR/validation_${timestamp}.json"
    local text_file="$REPORTS_DIR/validation_${timestamp}.txt"
    
    console_section_header "GENERATING REPORTS"
    echo ""
    
    # Generate JSON report
    console_progress "Generating JSON report..."
    generate_json_report "$json_file"
    
    # Generate text report
    console_progress "Generating text report..."
    generate_text_report "$text_file"
    
    echo ""
    console_info "Reports saved to: $REPORTS_DIR"
}

# =============================================================================
# Utility Functions
# =============================================================================

# Format duration in human-readable format
# Usage: format_duration <seconds>
format_duration() {
    local seconds=$1
    local minutes=$((seconds / 60))
    local remaining_seconds=$((seconds % 60))
    
    if [ $minutes -gt 0 ]; then
        echo "${minutes}m ${remaining_seconds}s"
    else
        echo "${seconds}s"
    fi
}

# Get timestamp
# Usage: get_timestamp
get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Calculate duration between two timestamps
# Usage: calculate_duration <start_time> <end_time>
calculate_duration() {
    local start_time="$1"
    local end_time="$2"
    
    local start_epoch=$(date -d "$start_time" +%s 2>/dev/null || echo "0")
    local end_epoch=$(date -d "$end_time" +%s 2>/dev/null || echo "0")
    
    echo $((end_epoch - start_epoch))
}
