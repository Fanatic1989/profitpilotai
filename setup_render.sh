cat > setup_render.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Render setup with Poetry..."
echo "🧹 Cleaning old build caches..."
rm -rf .venv __pycache__ .mypy_cache .pytest_cache

echo "✅ Creating runtime.txt for Python 3.11..."
echo "python-3.11.9" > runtime.txt

echo "✅ Checking for pyproject.toml..."
if [ ! -f pyproject.toml ]; then
    echo "❌ pyproject.toml missing. Creating..."
    cat > pyproject.toml << 'EOT'
[tool.poetry]
name = "profitpilotai"
version = "0.1.0"
description = "ProfitPilotAI - FastAPI backend with Supabase, Telegram Bot, and Deriv WebSocket"
authors = ["Your Name <your-email@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "0.111.0"
uvicorn = "0.30.1"
supabase = "2.4.0"
python-dotenv = "1.0.1"
requests = "2.32.3"
httpx = "0.27.0"
aiohttp = "3.9.5"
pandas = "2.2.2"
numpy = "1.26.4"
python-telegram-bot = "21.4"
websockets = "12.0"
loguru = "0.7.2"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOT
fi

echo "✅ Installing Poetry dependencies locally..."
poetry install

echo "✅ Render setup complete! Push to GitHub and redeploy."
EOF

chmod +x setup_render.sh
