from flask import Flask, request, jsonify
import pandas as pd
import os
import psycopg2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import json     # <-- NEW: For JSON handling
import atexit   # <-- NEW: For cleanup

app = Flask(__name__)

@app.route('/')
def home():
    return "TasteRealm API is running! Endpoints: /submit_survey (POST) and /recommendations (GET)"

# ===== NEW: SQLite Database Setup =====
DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        preferences TEXT
    );
""")
conn.commit()

# Create the dishes table if it doesn't already exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS dishes (
        dish_id SERIAL PRIMARY KEY,
        name TEXT,
        sweet INTEGER,
        salty INTEGER,
        sour INTEGER,
        bitter INTEGER,
        umami INTEGER,
        spice INTEGER
    );
""")
conn.commit()


# ===== Save a user's preferences =====
def save_user(user_id, data):
    """Save user preferences to Postgres"""
    cursor.execute(
        """
        INSERT INTO users (user_id, preferences)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET preferences = EXCLUDED.preferences;
        """,
        (user_id, json.dumps(data))
    )
    conn.commit()

def get_user(user_id):
    """Retrieve user preferences from SQLite"""
    cursor.execute("SELECT preferences FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result else None
# ===== END NEW =====

# ===== Sample Dishes Database (6-dimensional taste profiles) =====
sample_dishes = [
    {"dish_id": 1, "name": "Margherita Pizza",   "sweet": 2, "salty": 4, "sour": 1, "bitter": 1, "umami": 5, "spice": 1},
    {"dish_id": 2, "name": "Tonkotsu Ramen",      "sweet": 1, "salty": 5, "sour": 1, "bitter": 1, "umami": 9, "spice": 2},
    {"dish_id": 3, "name": "Pad Thai",            "sweet": 5, "salty": 4, "sour": 4, "bitter": 0, "umami": 6, "spice": 3},
    {"dish_id": 4, "name": "Buffalo Wings",       "sweet": 1, "salty": 6, "sour": 1, "bitter": 0, "umami": 5, "spice": 7},
    {"dish_id": 5, "name": "Guacamole",           "sweet": 1, "salty": 2, "sour": 3, "bitter": 0, "umami": 2, "spice": 2},
    {"dish_id": 6, "name": "Beef Pho",            "sweet": 2, "salty": 5, "sour": 2, "bitter": 0, "umami": 8, "spice": 1},
    {"dish_id": 7, "name": "Chocolate Mousse",    "sweet": 5, "salty": 1, "sour": 0, "bitter": 1, "umami": 1, "spice": 0},
]

# Convert to a DataFrame for easy slicing below
dishes = pd.DataFrame(sample_dishes)


    @app.route('/submit_survey', methods=['POST'])
    def submit_survey():
        """Endpoint to store user survey responses"""
        try:
            # 1) Grab the raw JSON payload from Typeform
            payload   = request.json
            form      = payload["form_response"]
            answers   = form["answers"]

            # 2) Flatten the nested answers into a simple dict
            flat = {}
            for ans in answers:
                key = ans["field"]["ref"]
                if ans["type"] == "number":
                    flat[key] = ans["number"]
                else:
                    flat[key] = ans.get("choices", {}).get("labels", [])

            # 3) Build your final survey dict
            data = {
                "user_id":                  form["token"],
                "flavors": {
                    "sweet":      flat.get("sweet", 0),
                    "salty":      flat.get("salty", 0),
                    "sour":       flat.get("sour", 0),
                    "bitter":     flat.get("bitter", 0),
                    "umami":      flat.get("umami", 0),
                    "spice":      flat.get("spice_tolerance", 0),
                },
                "textures":                 flat.get("textures", []),
                "cuisines":                 flat.get("cuisines", []),
                "spice_tolerance":          flat.get("spice_tolerance", 0),
                "dietary_restrictions":     flat.get("dietary_restrictions", []),
                "allergies":                flat.get("allergies", [])
            }

            # 4) Now validate & save exactly as before
            required_fields = ['user_id', 'flavors', 'textures', 'cuisines', 'spice_tolerance']
            for field in required_fields:
                if field not in data:
                    return jsonify({"status":"error","message":f"Missing field: {field}"}), 400

            save_user(
                data['user_id'],
                {
                    "flavors":           data['flavors'],
                    "textures":          data['textures'],
                    "cuisines":          data['cuisines'],
                    "spice_tolerance":   data['spice_tolerance'],
                    "dietary_restrictions": data.get('dietary_restrictions', []),
                    "allergies":            data.get('allergies', [])
                }
            )

            return jsonify({"status": "success", "user_id": data['user_id']})

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500


import traceback, sys

@app.route('/add_dish', methods=['POST'])
def add_dish():
    try:
        data = request.get_json()
        # Required fields
        required = ["name", "sweet", "salty", "sour", "bitter", "umami", "spice"]
        for key in required:
            if key not in data:
                return jsonify({"error": f"Missing field: {key}"}), 400

        cursor.execute(
            """
            INSERT INTO dishes (name, sweet, salty, sour, bitter, umami, spice)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING dish_id;
            """,
            (data["name"], data["sweet"], data["salty"], data["sour"],
             data["bitter"], data["umami"], data["spice"])
        )
        dish_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"status": "added", "dish_id": dish_id}), 201

    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return jsonify({"error": str(e)}), 500


@app.route('/recommendations', methods=['GET'])
def recommendations():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        # 1) Load the user's saved preferences from Postgres
        cursor.execute("SELECT preferences FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "User not found"}), 404

        preferences = json.loads(result[0])

        # 2) Build the user's 6-flavor taste vector
        user_vector = [
            preferences["flavors"].get("sweet", 0),
            preferences["flavors"].get("salty", 0),
            preferences["flavors"].get("sour", 0),
            preferences["flavors"].get("bitter", 0),
            preferences["flavors"].get("umami", 0),
            preferences.get("spice_tolerance", 0)
        ]

        # 3) Pull all dishes out of Postgres
        cursor.execute("""
         SELECT name, sweet, salty, sour, bitter, umami, spice
         FROM dishes;
        """)
        rows = cursor.fetchall()
        if not rows:
         return jsonify([])  # no dishes in the database yet

        # 4) Build a DataFrame from those rows
        import pandas as pd
        dishes_df = pd.DataFrame(rows, columns=[
         "name", "sweet", "salty", "sour", "bitter", "umami", "spice"
     ])

        # 5) Compute cosine similarity
        dish_vectors = dishes_df[["sweet","salty","sour","bitter","umami","spice"]].values
        sims = cosine_similarity([user_vector], dish_vectors)[0]

        # 6) Attach scores & pick top 5
        dishes_df["similarity"] = sims
        top_dishes = (
         dishes_df
         .sort_values("similarity", ascending=False)
         .head(5)["name"]
         .tolist()
     )

        return jsonify(top_dishes)

        # 4) Compute cosine similarity between the user and each dish
        similarities = cosine_similarity([user_vector], dish_vectors)[0]

        # 5) Attach scores and pick the top 5
        dishes["similarity"] = similarities
        top_dishes = (
            dishes
            .sort_values("similarity", ascending=False)
            .head(5)["name"]
            .tolist()
        )

        return jsonify(top_dishes)

    except Exception as e:
        # Log the full traceback to Render’s logs
        import traceback, sys
        traceback.print_exc(file=sys.stdout)
        return jsonify({"error": str(e)}), 500

# ===== NEW: Cleanup handler =====
def close_db():
    conn.close()
atexit.register(close_db)
# ===== END NEW =====

if __name__ == '__main__':
    app.run(debug=True, port=5000)