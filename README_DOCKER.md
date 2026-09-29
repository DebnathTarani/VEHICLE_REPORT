Vehicle Report Application - Docker Quick Start

Prerequisites
-------------
Docker Engine 24+ and Docker Compose V2 installed locally.

Convenient Commands

# *** Development ***
make dev      # up + build container, app on http://localhost:5010
make logs-dev # tail logs
docker ps -a  # list containers
docker compose down

# *** Production ***
make prod       # up + build image in production
docker compose -f docker-compose.prod.yml down

Run docker-compose.yml (dev):
docker compose up -d --build

Run docker-compose.prod.yml (prod):
docker compose -f docker-compose.prod.yml up -d --build

Stop containers:
docker compose down         # stop dev
docker compose -f docker-compose.prod.yml down  # stop prod

📂 Data Volume
The SQLite database lives in `/data/vehicle_reports.db` inside the container.
To persist across container restarts, mount this directory to a host volume.

docker compose -f docker-compose.prod.yml run --rm app python app.py

Disable ai modes:
Set VLLM_ENABLED=true with VLLM_HOST / VLLM_MODEL or set GOOGLE_API_KEY

or:
