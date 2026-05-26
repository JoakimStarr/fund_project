#!/bin/bash
MODE=${1:-dev}
if [ "$MODE" = "dev" ]; then
    echo "Starting in dev mode..."
    cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    cd frontend && npm run dev &
    wait
elif [ "$MODE" = "docker" ]; then
    echo "Starting in docker mode..."
    docker-compose up --build
else
    echo "Usage: ./start.sh [dev|docker]"
fi