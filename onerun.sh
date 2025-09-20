#!/bin/bash

/home/ahnaf/.local/bin/uv sync
/home/ahnaf/.local/bin/uv run python -m uvicorn main:app  --port 8000
