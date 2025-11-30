"""
test_gen_API_wState.py

FastAPI service that:
- Runs a stateful Google ADK agent to generate test data.
- Calls an upstream API-under-test with the generated record.
- Exposes debugging endpoints to dump the SQLite databases.

Usage:
    python test_gen_API_wState
"""
# Author: Bogdan Alexandru Georgescu
# Project: Agents Membership Monitoring Application (AgentsMMA) – Test Generator API
# Python: 3.11

import io
import contextlib
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, Union
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, Header, Response
import uvicorn
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import ADK components (silently during module load)
try:
    from typing import Any, Dict
    from google.adk.agents import Agent, LlmAgent
    from google.adk.apps.app import App, EventsCompactionConfig
    from google.adk.models.google_llm import Gemini
    from google.adk.sessions import DatabaseSessionService
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner
    from google.adk.tools.tool_context import ToolContext
    from google.genai import types
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools import google_search
    from google.genai import types
except ImportError as e:
    print(f"❌ ADK Import Error: {e}")
    raise

# Imports for Database Tool ---
from database_local import save_contact_to_db, create_all_tables # Import db functions

# Pydantic Model for Tool Input (based on schemas.py/ContactBase) ---
class ContactRecordInput(BaseModel):
    """Schema for a full contact record passed to the database tool."""
    first_name: str
    last_name: str
    hebrew_name: str 

    birth_date: datetime
    birth_date_day_h:int 
    birth_date_month_h:int
    birth_date_year_h:int
    
    phone_primary: str    
    phone_secondary: str   
    email: str
    address: str
    city: str
    country: str
    province: str    
    notes: str

# ADK Tool Function for writing contact record to database
async def write_contact_to_database(
    first_name: str,
    last_name: str,
    hebrew_name: str,
    birth_date: str,          # ISO string, e.g. "1976-01-16"
    birth_date_day_h: int,
    birth_date_month_h: int,
    birth_date_year_h: int,
    phone_primary: str,
    phone_secondary: str,
    email: str,
    address: str,
    city: str,
    province: str,
    country: str,
    notes: str,
) -> str:
    """
    Writes a structured contact record into the database.

    ADK will call this tool with simple JSON fields.
    `birth_date` should be an ISO date string, e.g. "1976-01-16".
    """
    try:
        # Parse birth_date string into datetime
        try:
            birth_dt = datetime.fromisoformat(birth_date)
        except ValueError:
            # Fallback if the model gives something slightly off
            return f"Failed to parse birth_date '{birth_date}' as ISO date."

        contact_data = {
            "first_name": first_name,
            "last_name": last_name,
            "hebrew_name": hebrew_name,
            "birth_date": birth_dt,
            "birth_date_day_h": birth_date_day_h,
            "birth_date_month_h": birth_date_month_h,
            "birth_date_year_h": birth_date_year_h,
            "phone_primary": phone_primary,
            "phone_secondary": phone_secondary,
            "email": email,
            "address": address,
            "city": city,
            "province": province,
            "country": country,
            "notes": notes,
            # created_at / updated_at are filled by SQLAlchemy defaults
        }

        msg, new_id = await save_contact_to_db(contact_data)  
        return f"{msg} New contact id={new_id}."

    except Exception as e:
        return f"Failed to save contact record to database: {e}"


# Variables for ADK Runner with State
APP_NAME = "agents"  # Application
USER_ID = "default"  # User
SESSION = "default"  # Session


# Initialize runner only once
runner = None

# SQLite database will be created automatically
db_url = "sqlite:///Test_Generator_State.db"  # Local SQLite file
session_service = DatabaseSessionService(db_url=db_url)

# Thanks to the course authors for this pattern!
def get_runner():
    global runner
    if runner is None:
        # Set up Google GenAI configuration (only once)
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        print("✅ Google GenAI configuration set.")
        print("✅ ADK components imported successfully.")
        
        root_agent = LlmAgent(
            name="Test_Generator",
            model="gemini-2.5-flash",
            description="A simple agent that can generate test data.",
        instruction=(
            "You are a Test Generator agent running inside Google ADK.\n"
            "- If the user asks what they said earlier in this session, answer from the prior turns you see.\n"
            "When you have a complete contact record (names, dates, phones, address, etc.), you may call "
            "the `write_contact_to_database` tool with the appropriate fields. Use ISO YYYY-MM-DD for birth_date."
        ),

            tools=[write_contact_to_database],
        )
        print("✅ Root Agent defined.")

        # Confirm model is set
        print(f"✅ Model in use: {root_agent.model}")       
        
        # Create a new runner with persistent storage
        runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
        print("✅ Runner with state created.")
    return runner


# logging setup
log = logging.getLogger("test_gen_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    yield

app = FastAPI(title="Test Generator API", lifespan=lifespan)

# CORS settings
# Allow the HTTP/HTML server on 8002 to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8002"],  # front-end origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FrontendRequest(BaseModel):
    test_prompt: str  # string from the browser

class FrontendResponse(BaseModel):
    agent_generated_test_data: str      # record generated by agent of the test generator API
    test_results_from_API: str          # results from API under test

@app.post("/generate_test", response_model=FrontendResponse)
async def gen_test(
    payload: FrontendRequest,
) -> Response:

    prompt = payload.test_prompt

    agent_generated_test_data: str = ""
    data_from_API_under_test: Dict[str, str] = {"result": ""}

    full_agent_response = ""

    # Process the text with Google ADK agent
    try:
        # Get the runner and process the prompt
        runner_instance = get_runner()


        app_name = runner_instance.app_name
        try:
            session = await session_service.create_session(app_name=app_name, user_id=USER_ID, session_id=SESSION)
        except:
            session = await session_service.get_session(app_name=app_name, user_id=USER_ID, session_id=SESSION)

        if prompt:
            log.info(f"Running agent with prompt: {prompt}")

            prompt=types.Content(role="user", parts=[types.Part(text=prompt)])
            
            # Iterate over the async event stream
            async for event in runner_instance.run_async(
                user_id=USER_ID, session_id=session.id, new_message=prompt
            ):
                
                log.debug(f"Event received: {event}")
                # Check for content and if it has text parts
                if event.content and event.content.parts:
                         # Filter out empty or "None" responses before printing
                        if (
                            event.content.parts[0].text != "None"
                            and event.content.parts[0].text
                        ):
                            log.info(f"Agent output part: {event.content.parts[0].text}")
                            full_agent_response += event.content.parts[0].text

            # After the stream finishes, set the final extracted text
            # This logic should be placed OUTSIDE the 'async for' loop
            if full_agent_response.strip().startswith("Contact("):
                agent_generated_test_data = full_agent_response.strip()
            else:
                # If the agent outputted status messages or other text before the final record
                agent_generated_test_data = full_agent_response.strip()

            log.info(f"Final Extracted Contact Record: {agent_generated_test_data}")
        
        else:
            log.info(f"No prompt provided by frontend.") 

        # Get API URL from environment variables
        api_under_test_url = os.getenv("API_UNDER_TEST_URL","http://localhost:8080/to_be_tested")
        if not api_under_test_url:
            raise ValueError("API_UNDER_TEST_URL environment variable is not set")
            
       # Call the API under test with generated test data. 
       # Note: only after the test generator agent replied.
       # Note: timeout increased to 120s for slow responses.
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                log.info("Calling API under test: %s", api_under_test_url)
                log.info("Payload: %r", {"record": agent_generated_test_data})

                resp = await client.post(
                    api_under_test_url,
                    json={"record": agent_generated_test_data},
                )

                log.info("Upstream status: %s", resp.status_code)
                log.info("Upstream raw body: %s", resp.text)

                resp.raise_for_status()
                data_from_API_under_test = resp.json()
                log.info("Upstream JSON parsed: %s", data_from_API_under_test)

            except httpx.ReadTimeout as e:
                log.error("Timeout calling API under test: %r", e)
                data_from_API_under_test = {"result": "Timeout calling API under test."}

            except httpx.RequestError as e:
                log.error("Network error calling API under test: %r", e)
                data_from_API_under_test = {"result": f"Network error calling API under test: {e}"}

    except Exception as e:
        log.error("ADK processing error: %s", str(e))
        if not agent_generated_test_data:
            agent_generated_test_data = f"Error generating test data: {e}"
        if not data_from_API_under_test["result"]:
            data_from_API_under_test["result"] = "Not calling API under test."

    # Build response for frontend (only after the API under test agent replied)
    return FrontendResponse(
        agent_generated_test_data=agent_generated_test_data,
        test_results_from_API=data_from_API_under_test["result"],
    )

# --- Debugging endpoints to dump the SQLite databases ---

# import sqlite3 for DB access
import sqlite3

# FastAPI imports required for DB dump endpoints
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse


# This is the Generated Tests DB section.
TGDB_PATH = os.getenv("GENERATED_TESTS_DB_PATH", "GeneratedTests.db")

@app.get("/TGdb-dump", response_class=PlainTextResponse)
async def get_TGdb_dump() -> PlainTextResponse:
    """
    Return a SQLite dump (SQL statements) of the database as plain text.
    """
    if not os.path.exists(TGDB_PATH):
        raise HTTPException(status_code=404, detail=f"Database file not found: {TGDB_PATH}")

    # Build the SQL dump in memory
    conn = sqlite3.connect(TGDB_PATH)
    try:
        buf = io.StringIO()
        for line in conn.iterdump():
            buf.write(f"{line}\n")
        dump_text = buf.getvalue()
    finally:
        conn.close()

    # Return as text, with a suggested download filename
    return PlainTextResponse(
        content=dump_text,
        headers={
            "Content-Disposition": 'attachment; filename="db_dump.sql"'
        },
    )

# This is the Passed Tests DB section.
TVDB_PATH = os.getenv("PASSED_TESTS_DB_PATH", "PassedTests.db")

@app.get("/TVdb-dump", response_class=PlainTextResponse)
async def get_TVdb_dump() -> PlainTextResponse:
    """
    Return a SQLite dump (SQL statements) of the database as plain text.
    """
    if not os.path.exists(TVDB_PATH):
        raise HTTPException(status_code=404, detail=f"Database file not found: {TVDB_PATH}")

    # Build the SQL dump in memory
    conn = sqlite3.connect(TVDB_PATH)
    try:
        buf = io.StringIO()
        for line in conn.iterdump():
            buf.write(f"{line}\n")
        dump_text = buf.getvalue()
    finally:
        conn.close()

    # Return as text, with a suggested download filename
    return PlainTextResponse(
        content=dump_text,
        headers={
            "Content-Disposition": 'attachment; filename="db_dump.sql"'
        },
    )

# This is the Test Generator States DB section.
TSDB_PATH = os.getenv("TEST_GEN_STATES_DB_PATH", "Test_Generator_State.db")

@app.get("/TSdb-dump", response_class=PlainTextResponse)
async def get_TVdb_dump() -> PlainTextResponse:
    """
    Return a SQLite dump (SQL statements) of the database as plain text.
    """
    if not os.path.exists(TSDB_PATH):
        raise HTTPException(status_code=404, detail=f"Database file not found: {TSDB_PATH}")

    # Build the SQL dump in memory
    conn = sqlite3.connect(TSDB_PATH)
    try:
        buf = io.StringIO()
        for line in conn.iterdump():
            buf.write(f"{line}\n")
        dump_text = buf.getvalue()
    finally:
        conn.close()

    # Return as text, with a suggested download filename
    return PlainTextResponse(
        content=dump_text,
        headers={
            "Content-Disposition": 'attachment; filename="db_dump.sql"'
        },
    )

# Run the FastAPI app with Uvicorn. You can set PORTA in .env or environment.
if __name__ == "__main__":
    port = int(os.getenv("PORTA", "8090"))
    print(f"Test generator API on :{port}")
    uvicorn.run("test_gen_API_wState:app", host="0.0.0.0", port=port, reload=False)
