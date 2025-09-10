from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import HTTPException

app = FastAPI(title="AI Parenting Assistant Suite")

# load dotenv robustly (tries utf-8-sig etc.)
dotenv_path = "OPENAI_API_KEY.env"
_loaded = False
for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
    try:
        load_dotenv(dotenv_path, override=False, encoding=enc)
        if os.getenv("OPENAI_API_KEY"):
            print(f"[INFO] Loaded OPENAI_API_KEY.env using encoding: {enc}")
            _loaded = True
            break
    except Exception as ex:
        print(f"[WARN] load_dotenv failed with encoding {enc}: {ex}")

if not _loaded:
    print("[WARN] OPENAI_API_KEY may not be loaded. Ensure OPENAI_API_KEY.env exists and is UTF-8 text.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("[ERROR] OPENAI_API_KEY is not set. Create OPENAI_API_KEY.env with: OPENAI_API_KEY=sk-...")
# Note: server will still start; endpoint will return 500 if key missing.

# Use OpenAI SDK (install: pip install openai python-dotenv)
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception as e:
    print("[ERROR] Failed to import OpenAI client. Make sure 'openai' package is installed.", e)
    openai_client = None

# Now the endpoint
@app.post("/api/generate-support")
async def api_generate_support(request: Request):
    """
    Expects JSON body: { "entry": { "mood": "...", "user_type": "...", "intensity": "...", "trigger": "...", "behaviors":"...", "notes":"...", "affirmation":"...", "timestamp":"..." } }
    Returns: { message, suggestion, affirmation } (or with _rawModelOutput on fallback)
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    entry = body.get("entry")
    if not entry:
        raise HTTPException(status_code=400, detail="Request body must contain 'entry' object")

    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized on server (missing OPENAI_API_KEY)")

    # Build prompts (explicit: return JSON only)
    system_prompt = (
        "You are a compassionate caregiver assistant. Produce a short empathic supportive message (1-2 sentences), "
        "one brief practical suggestion (1 line), and a short affirmation (one sentence). "
        "RETURN ONLY VALID JSON with keys exactly: \"message\", \"suggestion\", \"affirmation\". "
        "Example:\n"
        '{"message":"I can see this has been hard — it\'s okay to feel upset right now.","suggestion":"Offer a calm hug and a short quiet activity like reading.","affirmation":"You are safe and loved."}\n'
        "Do not include any explanation or extra text outside the JSON object."
    )

    user_prompt = (
        f"Entry details:\n"
        f"mood: {entry.get('mood','—')}\n"
        f"user_type: {entry.get('user_type','—')}\n"
        f"intensity: {entry.get('intensity','—')}\n"
        f"trigger: {entry.get('trigger','—')}\n"
        f"behaviors: {entry.get('behaviors','—')}\n"
        f"notes: {entry.get('notes','—')}\n"
        f"affirmation: {entry.get('affirmation','—')}\n"
        f"timestamp: {entry.get('timestamp','—')}\n\n"
        "Return only the JSON object described."
    )

    # Compose request to OpenAI Chat Completions
    try:
        # use chat completions endpoint via python OpenAI client
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # change to model available in your account if needed
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6,
            max_tokens=300,
        )
    except Exception as exc:
        # OpenAI call failed
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {str(exc)}")

    # Extract assistant text robustly
    assistant_text = ""
    try:
        # typical shape: response.choices[0].message.content
        assistant_text = response.choices[0].message.content if getattr(response, "choices", None) else str(response)
    except Exception:
        assistant_text = str(response)

    # Try parse JSON from assistant_text
    parsed = None
    try:
        parsed = json.loads(assistant_text)
    except Exception:
        # try to find a JSON object substring
        m = None
        try:
            # assistant_text may be a dict-like string; convert to str
            s = str(assistant_text)
            import re
            match = re.search(r"\{[\s\S]*\}", s)
            if match:
                parsed = json.loads(match.group(0))
        except Exception:
            parsed = None

    # If parsed and valid, return it
    if parsed and parsed.get("message"):
        return parsed

    # fallback: return a safe message + raw output for debugging
    fallback = {
        "message": f"I can see this is hard — it's okay to feel {entry.get('mood','this way')}. You are not alone.",
        "suggestion": "Try a calming activity (deep breaths, quiet toy, or short reading).",
        "affirmation": entry.get("affirmation") or "You are safe and loved.",
        "_rawModelOutput": assistant_text
    }
    return fallback

# Load API key from OPENAI_API_KEY.env
load_dotenv("OPENAI_API_KEY.env")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Mount static files for minimal styling (e.g., Bootstrap/Tailwind from CDN)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Mock data classes
class PlannerInput(BaseModel):
    child_age: int
    school_schedule: str
    family_goals: str
    special_needs: str

class MealsInput(BaseModel):
    family_preferences: str
    dietary_restrictions: str
    budget: float

class EmotionsInput(BaseModel):
    user_type: str  # "parent" or "child"
    mood: str
    notes: str = None

# Home page with links to tools
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )

# --- PLANNER MODULE ---
@app.get("/planner", response_class=HTMLResponse)
async def planner_form(request: Request):
    return templates.TemplateResponse("planner_form.html", {"request": request})

@app.post("/planner", response_class=JSONResponse)
async def planner_submit(
    child_age: int = Form(...),
    school_schedule: str = Form(...),
    family_goals: str = Form(...),
    special_needs: str = Form(None)
):
    # Mock response
    return {
        "planner": {
            "child_age": child_age,
            "school_schedule": school_schedule,
            "family_goals": family_goals,
            "special_needs": special_needs,
            "suggested_routines": [
                "Morning routine at 7:30 AM",
                "Homework time at 5:00 PM",
                "Family dinner at 7:00 PM"
            ],
            "tips": [
                "Encourage regular sleep schedule.",
                "Discuss daily highlights at dinner."
            ]
        }
    }

# --- MEALS MODULE ---
@app.get("/meals", response_class=HTMLResponse)
async def meals_form(request: Request):
    return templates.TemplateResponse("meals_form.html", {"request": request})

@app.post("/meals", response_class=JSONResponse)
async def meals_submit(
    family_preferences: str = Form(...),
    dietary_restrictions: str = Form(...),
    budget: float = Form(...)
):
    # Mock response
    return {
        "meals": {
            "preferences": family_preferences,
            "restrictions": dietary_restrictions,
            "budget": budget,
            "meal_plan": [
                {"name": "Veggie Pasta", "nutrition": "350 kcal"},
                {"name": "Grilled Chicken Salad", "nutrition": "400 kcal"}
            ],
            "grocery_list": ["Pasta", "Chicken breast", "Lettuce", "Tomato", "Olive oil"]
        }
    }

# --- EMOTIONS MODULE ---
@app.get("/emotions", response_class=HTMLResponse)
async def emotions_form(request: Request):
    return templates.TemplateResponse("emotions_form.html", {"request": request})

@app.post("/emotions", response_class=JSONResponse)
async def emotions_submit(
    user_type: str = Form(...),
    mood: str = Form(...),
    notes: str = Form(None)
):
    try:
        # Build prompt
        system_prompt = (
            "You are a compassionate caregiver assistant. Based on the user's mood, "
            "produce a short supportive response, one practical suggestion, and an affirmation. "
            "Return ONLY valid JSON with keys: message, suggestion, affirmation."
        )
        user_prompt = f"""
        User type: {user_type}
        Mood: {mood}
        Notes: {notes or "—"}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # change to "gpt-4o" or "gpt-4" if needed
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6,
            max_tokens=200,
        )

        text_output = response.choices[0].message.content.strip()

        # Try parsing JSON safely
        try:
            parsed = json.loads(text_output)
        except json.JSONDecodeError:
            # Try to extract first JSON-like substring
            start = text_output.find("{")
            end = text_output.rfind("}")
            if start != -1 and end != -1:
                parsed = json.loads(text_output[start:end+1])
            else:
                # Fallback default
                parsed = {
                    "message": "I hear you — it’s okay to feel this way.",
                    "suggestion": "Try taking a deep breath together.",
                    "affirmation": "You are safe and loved."
                }

        return {"emotions": {
            "user_type": user_type,
            "mood": mood,
            "notes": notes,
            "support": parsed
        }}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to generate supportive message", "detail": str(e)},
        )

# --- STRUCTURE FOR DB INTEGRATION ---
# Placeholder comments to indicate where DB logic will go (SQLite/Postgres)
# e.g., import SQLAlchemy, define models, CRUD operations, etc.

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)