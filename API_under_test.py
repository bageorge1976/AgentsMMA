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


# Import ADK components (silently during module load)
try:
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools import google_search
    from google.genai import types
except ImportError as e:
    print(f"❌ ADK Import Error: {e}")
    raise

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
            name="helpful_assistant",
            model="gemini-2.5-flash-lite",
            description="A simple agent that can answer general questions.",
            instruction="You are a helpful assistant. Use Google Search for current info or if unsure.",
            tools=[google_search],
        )
        print("✅ Root Agent defined.")
        
        runner = InMemoryRunner(agent=root_agent, app_name="agents")
        print("✅ Runner created.")
    return runner


log = logging.getLogger("api_under_test")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

app = FastAPI(title="API Under Test")

# Allow your HTML server on 8001 to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8002"],  # front-end origin
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
    #x_mailhook_token: Union[str, None] = Header(default=None)  # optional: read shared secret header
) -> Response:
    # Read raw body bytes


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

    prompt = f"""
    Prepare a validation_record string for the following contact record. I want the breakdown of the logic or steps for this rather complex task.
    In plain english explain your answer and give the rationale.
    In the validation_record use a new line after each Rule."""

    

    with open("rules.txt", "r", encoding="utf-8") as f:
        rules = f.read()


    # Process the text with Google ADK agent
    try:
        # Get the runner (creates it only once)
        current_runner = get_runner()
        
        # Use run_debug with the prompt
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            #events = await current_runner.run_debug(prompt + " " + payload.record + " " + rules )
            #events = await current_runner.run_debug(body["text"])
            events = await current_runner.run_debug(payload.record)

        # Take the last event and extract plain text from its parts
        if events:
            last_event = events[-1]
            agent_text = "".join(
                (getattr(part, "text", "") or "")
                for part in last_event.content.parts
            )
            log.info("Agent response: %s", agent_text)
        else:
            log.warning("No events received from ADK runner")
            
    except Exception as e:
        log.error("ADK processing error: %s", str(e))
        if not agent_text:
            agent_text = f"Error generating response: {e}"

    # Return 204 No Content like the original
    return ResponseToTestGeneratorAPI(result=agent_text)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"API under test on :{port}")
    uvicorn.run("API_under_test:app", host="0.0.0.0", port=port, reload=False)
