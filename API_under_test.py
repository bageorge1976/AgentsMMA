"""
API_under_test.py

FastAPI service that acts as the **API under test** in the Membership Monitoring
Application demo. This API:

- Exposes a POST /to_be_tested endpoint that receives a JSON payload
  of the form: {"record": "<agent_generated_contact_or_text>"}.
- Uses a Google ADK / Gemini-based "validator" agent to:
    * interpret the incoming record (usually a contact record)
    * run a series of validation rules (under_test_cmd.txt)
    * generate a detailed natural-language validation report
- Returns the validation narrative as JSON to the caller, typically the
  Test Generator API (on port 8090), which then forwards the result to
  the browser frontend (port 8002).

Typical usage:

    python API_under_test.py

This file is intentionally simple and focused on validating a single
`record` field, so it can be exercised by the test generator agent
as a black-box API.
"""

# Author: Bogdan Alexandru Georgescu
# Project: Membership Monitoring Application (MMA) – API Under Test
# Python: 3.11

import io
import contextlib
import os
import json
import logging
import asyncio
from typing import Any, Dict, Union
from urllib import response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, Header, Response
import uvicorn
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from datetime import datetime



# Import ADK components (silently during module load)
try:
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools import AgentTool, google_search
    from google.genai import types
except ImportError as e:
    print(f"❌ ADK Import Error: {e}")
    raise

# imports for Database Tool ---
from database_remote import save_contact_to_db, create_all_tables # Import db functions

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

# ADK Tool Function
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
    

# Child/Sub-Agent Definition
validation_narrator_agent = None

def get_validation_narrator_agent():
    """Defines and returns the specialized agent for generating verbose validation stories."""
    global validation_narrator_agent
    if validation_narrator_agent is None:
        validation_narrator_agent = Agent(

            # THIS NAME IS USED BY THE ROOT AGENT TO CALL THE TOOL
            name="ValidationNarratorAgent", 
            
            model="gemini-2.5-flash",
            description="A dedicated agent for generating verbose, structured narratives based on validation data. This agent's input is the full contact record.",
            instruction="""Your only job is to generate a detailed, verbose, and structured story based on the validation_record field of the input. 
            Do NOT attempt to write a contact record, call other tools, or perform calculations. 
            Analyze the validation_record (which is a semicolon-separated list of rules) and write a human-readable summary of every rule checked. 
            You **MUST** clearly mark each rule as '✅ Passed' or '❌ Failed'. 
            Always provide a final, prominent summary sentence about the overall record quality.""",
            tools=[], 
        )
    return validation_narrator_agent

# Initialize runner only once
runner = None

# Thanks to the course authors for this pattern!
def get_runner():
    global runner
    if runner is None:
        # Set up Google GenAI configuration (only once)
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        print("✅ Google GenAI configuration set.")
        print("✅ ADK components imported successfully.")
        
        # ✅ Make sure the child agent is created
        child = get_validation_narrator_agent()

        root_agent = Agent(
            name="Validation_Agent",
            model="gemini-2.5-flash",
            description="A simple agent that can validate contact records.",
            instruction=(
                "You are an Intelligent Validation Agent. "
                "1. Your first task is always to validate the contact record according to the rules provided step by step, providing the rationale."
                "2. Next, you MUST call the 'ValidationNarratorAgent' tool, passing the contact record, the validation_record and the rules to retrieve the detailed, verbose validation narrative from the sub-agent."
                "3. Then, you MUST call the 'write_contact_to_database' tool to persist the record."
                "4. Your final, complete response MUST be a combination of the verbose validation story (Step 2 result) and the database success message (Step 3 result). Be clear and verbose in your final summary."
            ),
            tools=[write_contact_to_database,AgentTool(agent=child)], 
        )
        print("✅ Root Agent defined.")
        
        runner = InMemoryRunner(agent=root_agent, app_name="agents")
        print("✅ Runner created.")
    return runner


log = logging.getLogger("api_under_test")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    yield

app = FastAPI(title="API Under Test", lifespan=lifespan)

# CORS settings
# This is only needed if you want to call this API from a front-end running on a different origin.
# Allow your HTML server on 8002 to call this API just in case.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8090"],  # front-end origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestFromTestGeneratorAPI(BaseModel):
    record: str  # string in, string out

class ResponseToTestGeneratorAPI(BaseModel):
    result: str

@app.post("/to_be_tested", response_model=ResponseToTestGeneratorAPI)
async def test_data(
    payload: RequestFromTestGeneratorAPI,
) -> Response:
    
    # This config type file contains the prompt instructions for the agent
    # Read raw body bytes
    with open("under_test_cmd.txt", "r", encoding="utf-8") as f:
        cmd_prompt = f.read()

    agent_text = ""  # initialize so it's always defined

    # Process the text with Google ADK agent
    try:
        current_runner = get_runner()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            events = await current_runner.run_debug(payload.record + " " + cmd_prompt)

        if events:
            last_event = events[-1]
            agent_text = "".join(
                (getattr(part, "text", "") or "")
                for part in last_event.content.parts
            )
            log.info("Agent response: %s", agent_text)
        else:
            log.warning("No events received from ADK runner")
            agent_text = "No events received from ADK runner."

    except Exception as e:
        log.error("ADK processing error: %s", str(e))
        if not agent_text:
            agent_text = f"Error generating response: {e}"

    return ResponseToTestGeneratorAPI(result=agent_text)

# Run the FastAPI app with Uvicorn. You can set PORTB in .env or environment.
if __name__ == "__main__":
    port = int(os.getenv("PORTB", "8080"))
    print(f"API under test on :{port}")
    uvicorn.run("API_under_test:app", host="0.0.0.0", port=port, reload=False)
