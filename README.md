# Agents Membership Monitoring Application (AgentsMMA)
# Frontend (8002) →  Test Generation API (8090) → Test Validation API (8080) → Test Generation API (8090) → Frontend (8002)

A frontend making user requests to a test generation API which sends test records to a validation API.

## Quickstart

**Make sure you have ports 8002, 8090, 8080 free.**
**Tested with Python 3.11.7.**


```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python API_under_test

python test_gen_API_wState.py

cd frontend
python frontend_server.py
```

## Point your browser to 8002. Enjoy!

