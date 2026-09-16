#Terminal 1
cd ~/Project/equation-golf
docker compose up db

#Terminal 2
cd ~/Project/equation-golf
nix develop
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

#Terminal 3
cd ~/Project/equation-golf
nix develop
npm run dev

# Seed development challenges (safe to run repeatedly)
python -m backend.seed_dev

# Seed 5,000 current-day demo submissions and archived leaderboards
python -m backend.seed_demo_data
