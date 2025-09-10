# main.py
"""
FastAPI entrypoint for the Parenting Assistant Suite (secure OpenAI usage).

Instructions:
 - For local development create a file named ".env" in project root with:
     OPENAI_API_KEY=sk-...
   and ensure ".env" is added to .gitignore (do NOT commit it).
 - In production (Render, Vercel, etc) set environment variable OPENAI_API_KEY in the service dashboard.
 - Start command on Render: uvicorn main:app --host 0.0.0.0 --port $PORT
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import os
import json
from dotenv import load_dotenv

# Attempt to load .env for local development only (safe: .env must be gitignored)
load_dotenv()  # will silently do nothing if no .env present

# Read key from environment (Render or host should set OPENAI_API_KEY)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client only if key present
openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        # Import or init failure — log it and keep openai_client as None
        print("[ERROR] Failed to import/init OpenAI client:", e)
else:
    print("[WARN] OPENAI_API_KEY not found in environment. OpenAI features will be disabled until set.")


app = FastAPI(title="AI Parenting Assistant Suite")

# Mount static and templates (adjust directories if your project layout differs)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ------------------------
# Helper: robust call to OpenAI chat
# ------------------------
def call_openai_chat(messages, model="gpt-4o-mini", temperature=0.6, max_tokens=300):
    """
    Calls the OpenAI chat completion via the installed OpenAI SDK.
    Returns the assistant text (string) or raises an Exception on failure.
    """
    if not openai_client:
        raise RuntimeError("OpenAI client not initialized (OPENAI_API_KEY missing)")

    # The OpenAI Python client surface may vary; this matches OpenAI SDK usage:
    resp = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    # Extract assistant content robustly
    try:
        # common shape: resp.choices[0].message.content
        return resp.choices[0].message.content
    except Exception:
        return str(resp)


# ------------------------
# Data Models (for future use)
# ------------------------
class PlannerInput(BaseModel):
    child_age: int
    school_schedule: str
    family_goals: str
    special_needs: str = None


class MealsInput(BaseModel):
    family_preferences: str
    dietary_restrictions: str
    budget: float


class EmotionsInput(BaseModel):
    user_type: str  # "parent" or "child"
    mood: str
    notes: str = None


# ------------------------
# Routes
# ------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# Planner routes (unchanged behavior)
@app.get("/planner", response_class=HTMLResponse)
async def planner_form(request: Request):
    return templates.TemplateResponse("planner_form.html", {"request": request})


@app.post("/planner", response_class=JSONResponse)
async def planner_submit(
    child_age: int = Form(...),
    school_schedule: str = Form(...),
    family_goals: str = Form(...),
    special_needs: str = Form(None),
):
    # Mock / placeholder logic: replace with real planner logic as needed
    return {
        "planner": {
            "child_age": child_age,
            "school_schedule": school_schedule,
            "family_goals": family_goals,
            "special_needs": special_needs,
            "suggested_routines": [
                "Morning routine at 7:30 AM",
                "Homework time at 5:00 PM",
                "Family dinner at 7:00 PM",
            ],
            "tips": [
                "Encourage regular sleep schedule.",
                "Discuss daily highlights at dinner.",
            ],
        }
    }


# Meals routes (unchanged behavior)
@app.get("/meals", response_class=HTMLResponse)
async def meals_form(request: Request):
    return templates.TemplateResponse("meals_form.html", {"request": request})


@app.post("/meals", response_class=JSONResponse)
async def meals_submit(
    family_preferences: str = Form(...),
    dietary_restrictions: str = Form(...),
    budget: float = Form(...),
):
    return {
        "meals": {
            "preferences": family_preferences,
            "restrictions": dietary_restrictions,
            "budget": budget,
            "meal_plan": [
                {"name": "Veggie Pasta", "nutrition": "350 kcal"},
                {"name": "Grilled Chicken Salad", "nutrition": "400 kcal"},
            ],
            "grocery_list": ["Pasta", "Chicken breast", "Lettuce", "Tomato", "Olive oil"],
        }
    }


# Emotions routes — secure OpenAI usage: backend calls OpenAI (no key exposed to frontend)
@app.get("/emotions", response_class=HTMLResponse)
async def emotions_form(request: Request):
    return templates.TemplateResponse("emotions_form.html", {"request": request})


@app.post("/emotions", response_class=JSONResponse)
async def emotions_submit(user_type: str = Form(...), mood: str = Form(...), notes: str = Form(None)):
    # Validate client initialization
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized (OPENAI_API_KEY missing)")

    # Build the system + user prompts that instruct model to return JSON only
    system_prompt = (
        "You are a compassionate caregiver assistant. Based on the user's mood, "
        "produce a short supportive response (1-2 sentences), one practical suggestion (1 line), and an affirmation (1 sentence). "
        "Return ONLY valid JSON with keys: message, suggestion, affirmation."
    )
    user_prompt = f"User type: {user_type}\nMood: {mood}\nNotes: {notes or '—'}"

    try:
        assistant_text = call_openai_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o-mini",
            temperature=0.6,
            max_tokens=200,
        )
    except Exception as e:
        # Bubble up a user-friendly error
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {str(e)}")

    # Try parsing JSON safely
    parsed = None
    try:
        parsed = json.loads(assistant_text.strip())
    except Exception:
        # Attempt to extract first JSON substring
        try:
            s = str(assistant_text)
            import re

            match = re.search(r"\{[\s\S]*\}", s)
            if match:
                parsed = json.loads(match.group(0))
        except Exception:
            parsed = None

    if parsed and isinstance(parsed, dict) and "message" in parsed:
        return {"emotions": {"user_type": user_type, "mood": mood, "notes": notes, "support": parsed}}
    else:
        # Fallback: safe default + raw model output for debugging
        fallback = {
            "message": "I hear you — it’s okay to feel this way.",
            "suggestion": "Try a deep breath together, or a short quiet activity.",
            "affirmation": "You are safe and loved.",
        }
        return {
            "emotions": {
                "user_type": user_type,
                "mood": mood,
                "notes": notes,
                "support": fallback,
                "_rawModelOutput": assistant_text,
            }
        }


# --- Placeholder area for DB integration, analytics, etc. ---

if __name__ == "__main__":
    # Local development: run uvicorn directly
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
