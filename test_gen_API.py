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
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools import google_search
    from google.genai import types
except ImportError as e:
    print(f"❌ ADK Import Error: {e}")
    raise

# --- NEW IMPORTS for Database Tool ---
from database_local import save_contact_to_db, create_all_tables # Import db functions

# --- NEW Pydantic Model for Tool Input (based on schemas.py/ContactBase) ---
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

# --- NEW ADK Tool Function ---
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

        msg, new_id = await save_contact_to_db(contact_data)  # returns (msg, id) :contentReference[oaicite:1]{index=1}
        return f"{msg} New contact id={new_id}."

    except Exception as e:
        return f"Failed to save contact record to database: {e}"

# Initialize runner only once
runner = None


def get_runner():
    global runner
    if runner is None:
        # Set up Google GenAI configuration (only once)
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        print("✅ Google GenAI configuration set.")
        print("✅ ADK components imported successfully.")
        
        root_agent = Agent(
            name="Test_Generator",
            model="gemini-2.5-flash",
            description="A simple agent that can generate test data.",
            instruction=(
                "You are a Test Generator. "
                "When you have a complete contact record (with names, dates, phones, address, etc.), "
                "call the `write_contact_to_database` tool with all the appropriate fields. "
                "Use ISO format for birth_date (YYYY-MM-DD). "
                #"Use Google Search for current info or if unsure."
            ),

            tools=[write_contact_to_database], #removed google_search
        )
        print("✅ Root Agent defined.")
        # ADD THIS LINE:
        print(f"✅ Model in use: {root_agent.model}")       
        runner = InMemoryRunner(agent=root_agent, app_name="agents")
        print("✅ Runner created.")
    return runner


log = logging.getLogger("test_gen_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    yield

app = FastAPI(title="Test Generator API", lifespan=lifespan)

# Allow your HTML server on 8001 to call this API
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
    agent_generated_test_data: str      # record generated by agent
    test_results_from_API: str          # results from API under test

@app.post("/generate_test", response_model=FrontendResponse)
async def gen_test(
    payload: FrontendRequest,
    #x_mailhook_token: Union[str, None] = Header(default=None)  # optional: read shared secret header
) -> Response:

    contact_record ="""
    Contact(first_name="Bogdan",
        last_name="Georgescu",
        hebrew_name= "בורגאן גאורגסקו",
        birth_date=datetime(1976,1,16),
        birth_date_day_h=14,
        birth_date_month_h=2, 
        birth_date_year_h=5776, 
        phone_primary="14032829220",    
        phone_secondary="15879669220",  
        email="bageorge1976@gmail.com",
        address="805 80 Point McKay CR NW",
        city="Calgary",
        province="Alberta",
        country="Canada",
        postal_code="T3B4W4",
        notes="A sample contact")  
    
    """

    prompt = payload.test_prompt

    #with open("r.txt", "r", encoding="utf-8") as f:
    #    rules = f.read()

    agent_generated_test_data: str = ""
    data_from_API_under_test: Dict[str, str] = {"result": ""}

    # Process the text with Google ADK agent
    try:
        # Get the runner (creates it only once)
        current_runner = get_runner()
        
        # Use run_debug with the prompt
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            events = await current_runner.run_debug(prompt)# + " " + rules )
            

        # --- START FIX: Robust extraction of the Contact record ---
        if events:
            # Look for the Contact record generated by the model in any turn
            for event in events:
                if event.content and event.content.role == 'model':
                    event_text = "".join(
                        (getattr(part, "text", "") or "")
                        for part in event.content.parts
                    )
                    
                    # Heuristic: Check if the text looks like the desired Contact record
                    if event_text.strip().startswith("Contact("):
                        agent_generated_test_data = event_text.strip()
                        break # Found the test data, stop searching

            # Log the entire events list for debugging and the extracted text
            log.info("ADK Events: %s", events) 
            log.info("Extracted Contact Record: %s", agent_generated_test_data)
        else:
            log.warning("No events received from ADK runner")
        # --- END FIX ---
            
        # Get API URL from environment variables
        api_under_test_url = os.getenv("API_UNDER_TEST_URL")
        if not api_under_test_url:
            raise ValueError("API_UNDER_TEST_URL environment variable is not set")
            
       # Call the API under test with generated test data
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
            data_from_API_under_test["result"] = "Error calling API under test."

    # Build response for frontend (only after B replied)
    return FrontendResponse(
        agent_generated_test_data=agent_generated_test_data,
        test_results_from_API=data_from_API_under_test["result"],
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8090"))
    print(f"Test generator API on :{port}")
    uvicorn.run("test_gen_API:app", host="0.0.0.0", port=port, reload=False)
