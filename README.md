# gameflix
the live site: https://gameflix-fawn.vercel.app/

gameflix show you the games everyone is playing on steam right now. You can save a game for later and leave a short note on it.

if you want to run it locally 

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
uvicorn app.main:app --reload
