# Dockerfile - Instructions for building the Docker image
# Each instruction creates a new layer in the image
# Layers are cached, so unchanged layers don't need to rebuild

# Step 1: Choose the base image
# python:3.12-slim = Official Python 3.12 image with minimal OS packages
# "slim" means smaller image size (faster downloads, less disk space)
# This is the foundation - everything else builds on top of this
FROM python:3.12-slim

# Step 2: Set metadata (optional but helpful for documentation)
# These labels help identify the image later
LABEL maintainer="learner@example.com"
LABEL description="Flask Excel Data Visualizer - Beginner-Friendly Docker Learning Project"

# Step 3: Set the working directory inside the container
# All commands (COPY, RUN, CMD) will execute from this directory
# Think of it like `cd /app` - we're organizing our files here
WORKDIR /app

# Step 4: Copy requirements.txt FIRST (Docker layer caching optimization)
# Why copy this separately? Docker caches each layer.
# If requirements.txt doesn't change, Docker reuses the cached layer
# This means we don't reinstall packages every time we change app.py
# This is a Docker best practice that saves build time!
COPY requirements.txt .

# Step 5: Install Python dependencies
# --no-cache-dir = Don't store pip's download cache (keeps image smaller)
# -r requirements.txt = Install all packages listed in requirements.txt
# This installs streamlit, pandas, plotly, and openpyxl
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Copy the application code and templates into the container
# We copy flask_app.py and templates directory
# Note: We copy this AFTER installing dependencies (another caching optimization)
# If only flask_app.py changes, we don't need to reinstall packages
COPY flask_app.py .
COPY templates/ templates/

# Step 7: Expose port 8501
# This tells Docker (and anyone reading this file) that the app uses port 8501
# We use 8501 to match docker-compose configuration
# This doesn't actually publish the port - that's done with -p flag in docker run
EXPOSE 8501

# Step 8: Set environment variables for Flask
# FLASK_ENV = development/production mode
# FLASK_APP = The Flask application file
ENV FLASK_ENV=production
ENV FLASK_APP=flask_app.py

# Step 9: Define the command to run when container starts
# python flask_app.py = Start the Flask app
# This is what actually launches your app!
CMD ["python", "flask_app.py"]
