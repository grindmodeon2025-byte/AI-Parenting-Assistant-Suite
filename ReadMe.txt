# My Planner (FastAPI)

How to run locally:
1. Create a virtual environment: python -m venv venv
2. Activate it:
   - Windows: venv\Scripts\activate
   - Mac/Linux: source venv/bin/activate
3. Install: pip install -r requirements.txt
4. Run: uvicorn main:app --reload

Note: Production start command (Render): uvicorn main:app --host 0.0.0.0 --port $PORT

# 👨‍👩‍👧 AI Parenting Assistant Suite

This project is an **AI-powered Parenting Assistant** that helps families with:  

- **🗓 Parenting Planner** – Create personalized daily/weekly plans for your child.  
- **🥗 Meal & Nutrition Assistant** – Generate healthy, kid-friendly meal plans with grocery lists.  
- **😊 Emotion Check-in & Affirmations** – Track moods and receive positive affirmations.  

It is built using **Flask** (Python web framework) and comes with a simple web interface (forms & pages).  

---

## 📂 Project Structure
ai-parenting-assistant/
│
├── main.py # Main program (Flask app)
├── requirements.txt # List of Python packages needed
├── templates/ # HTML files (web pages)
│ ├── home.html
│ ├── planner_form.html
│ ├── meals_form.html
│ └── emotions_form.html
└── static/ # (optional) place for CSS/images if needed
