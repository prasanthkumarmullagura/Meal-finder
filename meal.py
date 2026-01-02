import os
import json
import random
import requests
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

API_BASE = "https://www.themealdb.com/api/json/v1/1"
GEMINI_API_KEY = os.getenv("GEMINI_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_ingredient_count(meal):
    count = 0
    for i in range(1, 21):
        ing = meal.get(f"strIngredient{i}")
        if ing and ing.strip():
            count += 1
    return count

def fetch_full_details(basic_meals):
    full = []
    for m in basic_meals[:15]:
        r = requests.get(f"{API_BASE}/lookup.php?i={m['idMeal']}")
        if r.ok and r.json().get("meals"):
            meal = r.json()["meals"][0]
            meal['ingredient_count'] = get_ingredient_count(meal)
            full.append(meal)
    full.sort(key=lambda x: x['ingredient_count'])
    return full
# --- THE POSTMAN API ROUTE ---
@app.route("/api/search", methods=["GET"])
def api_search():
    s = request.args.get("s", "").strip()
    if not s:
        return jsonify({"error": "No search term provided"}), 400
    
    r = requests.get(f"{API_BASE}/search.php?s={s}")
    data = r.json().get("meals")
    
    if data:
        results = fetch_full_details(data)
        return jsonify({"results": results})
    
    return jsonify({"message": "No meals found", "results": []})

@app.route("/", methods=["GET", "POST"])
def index():
    error, search_term = False, ""
    top_priority, second_category, explore_meals = [], [], []
    
    if request.method == "POST":
        search_term = request.form.get("meal_name", "").strip()
        if search_term:
            r = requests.get(f"{API_BASE}/search.php?s={search_term}")
            data = r.json().get("meals")
            if data:
                detailed = fetch_full_details(data)
                top_priority = [m for m in detailed if m['ingredient_count'] <= 4]
                second_category = [m for m in detailed if m['ingredient_count'] > 4]
            else:
                error = True
    else:
        cat_r = requests.get(f"{API_BASE}/filter.php?c=Seafood")
        if cat_r.ok:
            explore_meals = cat_r.json().get("meals")[:12]

    return render_template("index.html", error=error, search_term=search_term, 
                           top_priority=top_priority, second_category=second_category, 
                           explore_meals=explore_meals)

@app.route("/meal/<meal_id>")
def meal_detail(meal_id):
    nutrition = {} # FIXED: Initialize as empty dict to avoid 'None' error
    r = requests.get(f"{API_BASE}/lookup.php?i={meal_id}")
    meal = r.json()["meals"][0] if r.ok and r.json().get("meals") else None
    
    if meal:
        meal['ingredient_count'] = get_ingredient_count(meal)
        if GEMINI_API_KEY:
            ings = [f"{meal.get('strMeasure'+str(i),'')} {meal.get('strIngredient'+str(i),'')}" for i in range(1,21) if meal.get('strIngredient'+str(i))]
            prompt = f"Return ONLY raw JSON for nutrition per 100g of {meal['strMeal']} with ingredients {ings}: {{\"Calories\": \"...\", \"Protein\": \"...\", \"Carbs\": \"...\", \"Fats\": \"...\"}}"
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                res = model.generate_content(prompt)
                clean_text = res.text.strip().replace("```json", "").replace("```", "").strip()
                nutrition = json.loads(clean_text)
            except:
                # Fallback dictionary if AI fails
                nutrition = {"Calories": "Estimate Ready", "Protein": "N/A", "Carbs": "N/A", "Fats": "N/A"}
                
    return render_template("meal_detail.html", meal=meal, nutrition=nutrition)

if __name__ == "__main__":
    app.run(debug=True)