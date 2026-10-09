#!/bin/bash
# Quick local dev setup

set -euo pipefail

echo "==> Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Setting up .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i.bak "s/your-secret-key-minimum-32-characters-long-change-this/$SECRET/" .env
    rm -f .env.bak
    echo "✅ .env created. Fill in your API keys."
else
    echo "⚠️  .env already exists, skipping."
fi

echo "==> Starting Docker services (Postgres + Redis)..."
cd infra/docker && docker-compose up -d postgres redis && cd ../..

echo "==> Waiting for Postgres to be ready..."
sleep 5

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your OpenAI/Gemini keys"
echo "  2. Run: source .venv/bin/activate && uvicorn main:app --reload"
echo "  3. Open: http://localhost:8000/docs"
echo ""
echo "To start Celery worker:"
echo "  celery -A core.queue.celery_app worker --loglevel=info"
