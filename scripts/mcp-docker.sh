#!/bin/bash

# MCP Servers Docker Management Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to show help
show_help() {
    echo "MCP Servers Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     - Start all MCP servers"
    echo "  stop      - Stop all MCP servers"
    echo "  restart   - Restart all MCP servers"
    echo "  status    - Show status of all services"
    echo "  logs      - Show logs for all services"
    echo "  logs <service> - Show logs for a specific service"
    echo "  build     - Build all Docker images"
    echo "  clean     - Stop and remove all containers and images"
    echo "  prune     - Clean up Docker resources (interactive)"
    echo "  prune images - Remove unused images"
    echo "  prune all    - Remove all unused Docker resources"
    echo "  prune system - Remove unused containers, networks, and build cache"
    echo "  health    - Check health of all services"
    echo "  help      - Show this help message"
    echo ""
    echo "Services:"
    echo "  - kanban-mcp (Port 8001)"
    echo "  - gmail-mcp (Port 8002)" 
    echo "  - example-mcp (Port 8003)"
    echo "  - kanban-frontend (Port 3000)"
}

# Function to start services
start_services() {
    print_status "Starting MCP servers..."
    docker-compose up -d
    print_success "All MCP servers started!"
    echo ""
    print_status "Services are available at:"
    echo "  • Kanban MCP Server: http://localhost:8001"
    echo "  • Gmail MCP Server: http://localhost:8002"
    echo "  • Example MCP Server: http://localhost:8003"
    echo "  • Kanban Frontend: http://localhost:3000"
}

# Function to stop services
stop_services() {
    print_status "Stopping MCP servers..."
    docker-compose down
    print_success "All MCP servers stopped!"
}

# Function to restart services
restart_services() {
    print_status "Restarting MCP servers..."
    docker-compose restart
    print_success "All MCP servers restarted!"
}

# Function to show status
show_status() {
    print_status "MCP Services Status:"
    docker-compose ps
}

# Function to show logs
show_logs() {
    if [ -n "$2" ]; then
        print_status "Showing logs for $2..."
        docker-compose logs -f "$2"
    else
        print_status "Showing logs for all services..."
        docker-compose logs -f
    fi
}

# Function to build images
build_images() {
    print_status "Building Docker images..."
    docker-compose build
    print_success "All images built successfully!"
}

# Function to clean up
clean_up() {
    print_warning "This will stop and remove all containers and images."
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cleaning up..."
        docker-compose down --rmi all --volumes --remove-orphans
        print_success "Cleanup completed!"
    else
        print_status "Cleanup cancelled."
    fi
}

# Function to check health
check_health() {
    print_status "Checking health of MCP services..."
    
    services=("kanban-mcp:8001" "gmail-mcp:8002" "example-mcp:8003")
    
    for service in "${services[@]}"; do
        name=$(echo "$service" | cut -d: -f1)
        port=$(echo "$service" | cut -d: -f2)
        
        if curl -f -s "http://localhost:$port/health" > /dev/null 2>&1; then
            print_success "$name is healthy"
        else
            print_error "$name is not responding"
        fi
    done
}

# Function to show Docker space usage
show_docker_usage() {
    print_status "Current Docker space usage:"
    docker system df
    echo ""
}

# Function to prune Docker resources
prune_docker() {
    local prune_type="${2:-interactive}"
    
    case "$prune_type" in
        images)
            print_status "Removing unused Docker images..."
            show_docker_usage
            print_warning "This will remove all unused images (not just dangling ones)."
            read -p "Continue? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker image prune -a -f
                print_success "Unused images removed!"
                show_docker_usage
            else
                print_status "Image cleanup cancelled."
            fi
            ;;
        system)
            print_status "Removing unused containers, networks, and build cache..."
            show_docker_usage
            print_warning "This will remove:"
            echo "  • Stopped containers"
            echo "  • Unused networks"
            echo "  • Dangling images"
            echo "  • Build cache"
            read -p "Continue? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker system prune -f
                print_success "System cleanup completed!"
                show_docker_usage
            else
                print_status "System cleanup cancelled."
            fi
            ;;
        all)
            print_status "Removing ALL unused Docker resources..."
            show_docker_usage
            print_warning "This will remove:"
            echo "  • Stopped containers"
            echo "  • Unused networks"
            echo "  • ALL unused images (not just dangling ones)"
            echo "  • Build cache"
            echo "  • Unused volumes"
            read -p "Are you sure? This is aggressive cleanup! (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker system prune -a -f --volumes
                print_success "Aggressive cleanup completed!"
                show_docker_usage
            else
                print_status "Cleanup cancelled."
            fi
            ;;
        interactive|*)
            print_status "Docker Cleanup Options:"
            show_docker_usage
            echo "Choose cleanup level:"
            echo "  1) Images only - Remove unused images"
            echo "  2) System - Remove containers, networks, build cache"
            echo "  3) All - Remove everything unused (aggressive)"
            echo "  4) Show usage only"
            echo "  5) Cancel"
            echo ""
            read -p "Select option (1-5): " -n 1 -r
            echo
            case $REPLY in
                1) prune_docker "" images ;;
                2) prune_docker "" system ;;
                3) prune_docker "" all ;;
                4) show_docker_usage ;;
                5) print_status "Cleanup cancelled." ;;
                *) print_error "Invalid option. Cleanup cancelled." ;;
            esac
            ;;
    esac
}

# Main script logic
case "${1:-help}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$@"
        ;;
    build)
        build_images
        ;;
    clean)
        clean_up
        ;;
    prune)
        prune_docker "$@"
        ;;
    health)
        check_health
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac 