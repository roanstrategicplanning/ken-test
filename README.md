# DataViz Pro - Streamlit Excel/CSV Data Visualizer

A powerful web application for visualizing Excel and CSV files with interactive charts and graphs. Built with Streamlit and Docker-ready.

## 🚀 Quick Start with Docker

### Prerequisites
- [Docker](https://www.docker.com/get-started) installed on your system
- Docker Desktop (for Mac/Windows) or Docker Engine (for Linux)

### Installation & Running

#### Option 1: Using Makefile (Recommended - Easiest)

The project includes a Makefile with simple commands:

```bash
# Build the Docker image
make build

# Start the application
make up

# View logs
make logs

# Stop the application
make down

# Clean up everything
make clean

# Fresh rebuild (clean + build + start)
make fresh
```

After running `make up`, open your browser to: **http://localhost:8501**

#### Option 2: Using Docker Compose (Simple)

```bash
# Build and start the application
docker-compose up --build

# Run in background (detached mode)
docker-compose up -d --build

# Stop the application
docker-compose down

# View logs
docker-compose logs -f
```

#### Option 3: Using Docker Commands Directly

```bash
# Build the Docker image
docker build -t streamlit-excel-visualizer .

# Run the container
docker run -d --name streamlit-app -p 8501:8501 streamlit-excel-visualizer

# View logs
docker logs -f streamlit-app

# Stop the container
docker stop streamlit-app

# Remove the container
docker rm streamlit-app
```

## 📋 Available Make Commands

| Command | Description |
|---------|-------------|
| `make build` | Build the Docker image |
| `make up` | Start the container (runs the app) |
| `make down` | Stop and remove the container |
| `make logs` | View container logs |
| `make status` | Check if container is running |
| `make clean` | Remove the image and container |
| `make rebuild` | Rebuild everything from scratch (no cache) |
| `make fresh` | Stop, clean, build, and start (all-in-one) |
| `make install` | Install Python dependencies (for non-Docker use) |
| `make run` | Run the app directly without Docker |

## 🛠️ Running Without Docker

If you prefer to run without Docker:

```bash
# Install dependencies
make install
# or manually: pip install -r requirements.txt

# Run the app
make run
# or manually: streamlit run app.py
```

## 📦 What's Included

- **Streamlit** - Web framework for data apps
- **Pandas** - Data manipulation and analysis
- **Plotly** - Interactive charting library
- **OpenPyXL** - Excel file reader/writer
- **NumPy** - Numerical computing

## ✨ Features

- 📊 Upload Excel (.xlsx, .xls) and CSV files
- 📈 Automatic chart generation (Line, Pie, Bar charts)
- 📥 Download processed data as Excel or CSV
- 🎨 Beautiful, modern UI
- ⚡ Fast processing of large files (up to 50MB, 100K rows)

## 🔧 Troubleshooting

### Port Already in Use
If port 8501 is already in use, you can change it:

**Using Docker:**
```bash
docker run -d --name streamlit-app -p 8502:8501 streamlit-excel-visualizer
```
Then access at http://localhost:8502

**Using Docker Compose:**
Edit `docker-compose.yml` and change `"8501:8501"` to `"8502:8501"`

### Container Won't Start
```bash
# Check if container exists
docker ps -a

# Remove old container
docker rm streamlit-app

# Rebuild and start fresh
make fresh
```

### View Logs for Debugging
```bash
make logs
# or
docker logs -f streamlit-app
```

## 📝 Notes

- The app processes files up to 50MB
- Maximum 100,000 rows are processed (for performance)
- Files are processed in chunks for large datasets

## 🐳 Docker Image Details

- **Base Image**: Python 3.12-slim
- **Working Directory**: /app
- **Port**: 8501
- **Default Command**: Streamlit app on port 8501

## 📄 License

This project is open source and available for use.

