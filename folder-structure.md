nederland-discounts/
├── .github/workflows/       # CI/CD (Auto-deploy scrapers)
├── apps/
│   ├── api/                 # FastAPI/Go server for the Mobile App
│   │   ├── routes/          # Endpoints (stores, discounts, user)
│   │   └── main.py
│   ├── workers/             # The Scrapers (Independent services)
│   │   ├── ah_worker.py     # Albert Heijn Scraper
│   │   ├── jumbo_worker.py  # Jumbo Scraper
│   │   └── base_worker.py   # Abstract class for scrapers
│   └── orchestrator/        # The "Agentic" layer (Data cleaning/Matching)
├── core/
│   ├── database/            # SQL Alchemy models & PostGIS logic
│   ├── geo/                 # H3 Indexing & distance logic
│   └── security/            # Auth & Guardrails
├── data/                    # Local storage for temp images/JSONs
├── infrastructure/
│   ├── docker-compose.yml   # Local Dev environment (Postgres + Redis)
│   └── terraform/           # Cloud infra (AWS/GCP)
├── requirements.txt
└── .env                     # API Keys, DB Credentials