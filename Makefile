# Makefile - Simple commands for building and running the Docker container
# Beginners can use: make build and make up
# No need to remember long docker commands!

# Variables (makes it easy to change values in one place)
IMAGE_NAME = streamlit-excel-visualizer
CONTAINER_NAME = streamlit-app
PORT = 8501

# Default target (runs when you just type "make")
.DEFAULT_GOAL := help

# Help target - shows available commands
help:
	@echo "Available commands:"
	@echo ""
	@echo "Running without Docker (recommended for development):"
	@echo "  make install  - Install Python dependencies"
	@echo "  make run      - Run the Streamlit app directly (no Docker)"
	@echo ""
	@echo "Running with Docker:"
	@echo "  make build    - Build the Docker image"
	@echo "  make up       - Run the container (starts the app)"
	@echo "  make down     - Stop and remove the container"
	@echo "  make logs     - View container logs"
	@echo "  make status   - Check if container is running"
	@echo "  make clean    - Remove the image and container"
	@echo "  make rebuild  - Rebuild everything from scratch"
	@echo "  make fresh    - Stop, clean, build, and start (all-in-one)"

# Build the Docker image
# docker build = Build an image from Dockerfile
# -t = Tag the image with a name (like giving it a label)
# . = Use current directory as build context (where Dockerfile is)
build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) .
	@echo "Build complete! Run 'make up' to start the app."

# Run the container
# docker run = Start a new container from the image
# -d = Run in detached mode (background)
# --name = Give the container a friendly name
# -p = Port mapping: HOST_PORT:CONTAINER_PORT
#   This maps localhost:8501 on your computer to port 8501 in the container
# $(IMAGE_NAME) = The image to run
up:
	@echo "Starting Streamlit app..."
	@echo "The app will be available at: http://localhost:$(PORT)"
	docker run -d --name $(CONTAINER_NAME) -p $(PORT):8501 $(IMAGE_NAME)
	@echo "Container started! Open http://localhost:$(PORT) in your browser."
	@echo "Check logs with: make logs"

# Stop and remove the container
down:
	@echo "Stopping container..."
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true
	@echo "Container stopped and removed."

# View container logs (useful for debugging)
logs:
	@echo "Showing logs for $(CONTAINER_NAME)..."
	@docker logs -f $(CONTAINER_NAME) || echo "Container not found. It may have stopped. Check with: docker ps -a"

# Check container status
status:
	@echo "Checking container status..."
	@docker ps -a --filter name=$(CONTAINER_NAME) || echo "No containers found with name $(CONTAINER_NAME)"

# Clean up: remove container and image
clean:
	@echo "Cleaning up..."
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true
	docker rmi $(IMAGE_NAME) || true
	@echo "Cleanup complete."

# Rebuild everything from scratch (no cache)
rebuild:
	@echo "Rebuilding from scratch..."
	docker build --no-cache -t $(IMAGE_NAME) .
	@echo "Rebuild complete! Run 'make up' to start the app."

# Fresh start: down, clean, build, and up in one command
fresh:
	@echo "Starting fresh rebuild..."
	$(MAKE) down
	$(MAKE) clean
	$(MAKE) build
	$(MAKE) up
	@echo "Fresh rebuild complete!"

# Install Python dependencies (for running without Docker)
install:
	@echo "Installing Python dependencies..."
	@if command -v pip3 >/dev/null 2>&1; then \
		pip3 install -r requirements.txt; \
	elif command -v pip >/dev/null 2>&1; then \
		pip install -r requirements.txt; \
	else \
		echo "Error: pip not found. Please install Python and pip first."; \
		exit 1; \
	fi
	@echo "Dependencies installed! Run 'make run' to start the app."

# Run Streamlit app directly (without Docker)
run:
	@echo "Starting Streamlit app..."
	@echo "The app will be available at: http://localhost:$(PORT)"
	@if command -v streamlit >/dev/null 2>&1; then \
		streamlit run app.py --server.port $(PORT); \
	else \
		echo "Error: streamlit not found. Installing dependencies..."; \
		$(MAKE) install; \
		streamlit run app.py --server.port $(PORT); \
	fi

