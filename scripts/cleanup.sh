#!/bin/bash

# Cleanup Script for Emergency Incident Management System
# This script cleans up log files and QR code files to free up disk space
# Usage: ./cleanup.sh [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
DRY_RUN=false
VERBOSE=false
LOGS_OLDER_THAN=7  # days
QR_OLDER_THAN=30   # days
FORCE=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

# Function to show help
show_help() {
    cat << EOF
Emergency Incident Management System - Cleanup Script

Usage: $0 [OPTIONS]

Options:
    -d, --dry-run           Show what would be deleted without actually deleting
    -v, --verbose           Show detailed output
    -l, --logs-days DAYS    Delete log files older than DAYS (default: 7)
    -q, --qr-days DAYS      Delete QR codes older than DAYS (default: 30)
    -f, --force             Don't ask for confirmation
    -h, --help              Show this help message

Examples:
    $0                      # Interactive cleanup with defaults
    $0 --dry-run            # Show what would be cleaned up
    $0 -l 3 -q 14          # Delete logs older than 3 days, QR codes older than 14 days
    $0 --force              # Clean up without asking for confirmation

Directories cleaned:
    logs/                   - Application log files
    static/qr_codes/        - Generated QR code images
    docker/logs/            - Docker container logs (if present)

EOF
}

# Function to parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -l|--logs-days)
                LOGS_OLDER_THAN="$2"
                shift 2
                ;;
            -q|--qr-days)
                QR_OLDER_THAN="$2"
                shift 2
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Function to check if directory exists and is writable
check_directory() {
    local dir="$1"
    local desc="$2"
    
    if [ ! -d "$dir" ]; then
        print_verbose "$desc directory does not exist: $dir"
        return 1
    fi
    
    if [ ! -w "$dir" ]; then
        print_error "$desc directory is not writable: $dir"
        return 1
    fi
    
    return 0
}

# Function to get file size in human readable format
get_size() {
    local path="$1"
    
    if command -v du &> /dev/null; then
        du -sh "$path" 2>/dev/null | cut -f1
    else
        echo "unknown"
    fi
}

# Function to count files
count_files() {
    local pattern="$1"
    find $pattern 2>/dev/null | wc -l
}

# Function to clean up log files
cleanup_logs() {
    local logs_dirs=("logs" "docker/logs")
    local total_files=0
    local total_size="0K"
    
    print_status "Cleaning up log files older than $LOGS_OLDER_THAN days..."
    
    for logs_dir in "${logs_dirs[@]}"; do
        if check_directory "$logs_dir" "Logs"; then
            print_verbose "Processing directory: $logs_dir"
            
            # Find log files older than specified days
            local old_logs
            old_logs=$(find "$logs_dir" -type f \( -name "*.log" -o -name "*.log.*" -o -name "*.out" \) -mtime +$LOGS_OLDER_THAN 2>/dev/null || true)
            
            if [ -n "$old_logs" ]; then
                local count
                count=$(echo "$old_logs" | wc -l)
                total_files=$((total_files + count))
                
                if [ "$VERBOSE" = true ]; then
                    echo "$old_logs" | while read -r file; do
                        if [ -f "$file" ]; then
                            local size
                            size=$(get_size "$file")
                            print_verbose "  Would delete: $file ($size)"
                        fi
                    done
                fi
                
                if [ "$DRY_RUN" = false ]; then
                    echo "$old_logs" | xargs rm -f
                    print_success "Deleted $count log files from $logs_dir"
                else
                    print_status "Would delete $count log files from $logs_dir"
                fi
            else
                print_verbose "No old log files found in $logs_dir"
            fi
        fi
    done
    
    # Clean up empty log directories
    for logs_dir in "${logs_dirs[@]}"; do
        if [ -d "$logs_dir" ] && [ -z "$(ls -A "$logs_dir" 2>/dev/null)" ]; then
            print_verbose "Log directory $logs_dir is empty, keeping directory structure"
        fi
    done
    
    if [ $total_files -gt 0 ]; then
        print_success "Log cleanup completed: $total_files files processed"
    else
        print_status "No log files needed cleanup"
    fi
}

# Function to clean up QR code files
cleanup_qr_codes() {
    local qr_dirs=("static/qr_codes" "docker/static/qr_codes")
    local total_files=0
    
    print_status "Cleaning up QR code files older than $QR_OLDER_THAN days..."
    
    for qr_dir in "${qr_dirs[@]}"; do
        if check_directory "$qr_dir" "QR codes"; then
            print_verbose "Processing directory: $qr_dir"
            
            # Find QR code files older than specified days
            local old_qr_codes
            old_qr_codes=$(find "$qr_dir" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) -mtime +$QR_OLDER_THAN 2>/dev/null || true)
            
            if [ -n "$old_qr_codes" ]; then
                local count
                count=$(echo "$old_qr_codes" | wc -l)
                total_files=$((total_files + count))
                
                if [ "$VERBOSE" = true ]; then
                    echo "$old_qr_codes" | while read -r file; do
                        if [ -f "$file" ]; then
                            local size
                            size=$(get_size "$file")
                            print_verbose "  Would delete: $file ($size)"
                        fi
                    done
                fi
                
                if [ "$DRY_RUN" = false ]; then
                    echo "$old_qr_codes" | xargs rm -f
                    print_success "Deleted $count QR code files from $qr_dir"
                else
                    print_status "Would delete $count QR code files from $qr_dir"
                fi
            else
                print_verbose "No old QR code files found in $qr_dir"
            fi
        fi
    done
    
    if [ $total_files -gt 0 ]; then
        print_success "QR code cleanup completed: $total_files files processed"
    else
        print_status "No QR code files needed cleanup"
    fi
}

# Function to clean up temporary files
cleanup_temp_files() {
    local temp_patterns=(
        "*.tmp"
        "*.temp" 
        "*.bak"
        "*.swp"
        "*.swo"
        "*~"
        ".DS_Store"
        "Thumbs.db"
    )
    
    print_status "Cleaning up temporary files..."
    
    local total_files=0
    
    for pattern in "${temp_patterns[@]}"; do
        local temp_files
        temp_files=$(find . -name "$pattern" -type f 2>/dev/null || true)
        
        if [ -n "$temp_files" ]; then
            local count
            count=$(echo "$temp_files" | wc -l)
            total_files=$((total_files + count))
            
            if [ "$VERBOSE" = true ]; then
                echo "$temp_files" | while read -r file; do
                    print_verbose "  Would delete: $file"
                done
            fi
            
            if [ "$DRY_RUN" = false ]; then
                echo "$temp_files" | xargs rm -f
                print_success "Deleted $count temporary files matching '$pattern'"
            else
                print_status "Would delete $count temporary files matching '$pattern'"
            fi
        fi
    done
    
    if [ $total_files -gt 0 ]; then
        print_success "Temporary file cleanup completed: $total_files files processed"
    else
        print_status "No temporary files needed cleanup"
    fi
}

# Function to show disk space usage
show_disk_usage() {
    print_status "Current disk usage for key directories:"
    
    local dirs=("logs" "static/qr_codes" "docker/logs" "docker/static/qr_codes")
    
    for dir in "${dirs[@]}"; do
        if [ -d "$dir" ]; then
            local size
            size=$(get_size "$dir")
            local file_count
            file_count=$(find "$dir" -type f 2>/dev/null | wc -l)
            echo "  $dir: $size ($file_count files)"
        fi
    done
}

# Function to get user confirmation
get_confirmation() {
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    echo
    read -p "Do you want to proceed with the cleanup? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# Main cleanup function
main() {
    echo "=== Emergency Incident Management System - Cleanup Script ==="
    echo
    
    # Parse command line arguments
    parse_args "$@"
    
    # Show current settings
    print_status "Cleanup Settings:"
    echo "  Dry Run: $DRY_RUN"
    echo "  Verbose: $VERBOSE"
    echo "  Log files older than: $LOGS_OLDER_THAN days"
    echo "  QR codes older than: $QR_OLDER_THAN days"
    echo "  Force: $FORCE"
    echo
    
    # Show current disk usage
    show_disk_usage
    echo
    
    # Get confirmation unless in dry run mode or force mode
    if [ "$DRY_RUN" = false ] && ! get_confirmation; then
        print_status "Cleanup cancelled by user"
        exit 0
    fi
    
    # Record start time
    local start_time
    start_time=$(date)
    
    # Perform cleanup
    cleanup_logs
    echo
    cleanup_qr_codes
    echo
    cleanup_temp_files
    echo
    
    # Show final disk usage
    if [ "$DRY_RUN" = false ]; then
        print_status "Updated disk usage:"
        show_disk_usage
    fi
    
    echo
    local end_time
    end_time=$(date)
    
    if [ "$DRY_RUN" = true ]; then
        print_success "Dry run completed! Use without --dry-run to actually delete files."
    else
        print_success "Cleanup completed successfully!"
    fi
    
    print_status "Started: $start_time"
    print_status "Finished: $end_time"
}

# Run the main function with all arguments
main "$@"
