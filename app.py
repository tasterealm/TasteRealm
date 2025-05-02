from flask import Flask, request, jsonify
import pandas as pd
import os
import psycopg2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import json     # <-- NEW: For JSON handling
import atexit   # <-- NEW: For cleanup
# at the top of app.py, after your imports
import pandas as pd

# replace this list with your full dish dataset (or load it from Postgres)
dish_list = [
    { "dish_id": 1, "name": "Margherita Pizza",       "sweet": 2, "salty": 4, "sour": 1, "bitter": 1, "umami": 5, "spice": 1 },
    { "dish_id": 2, "name": "Chocolate Mousse",       "sweet": 5, "salty": 1, "sour": 0, "bitter": 1, "umami": 1, "spice": 0 },
    { "dish_id": 3, "name": "Chicken Tikka Masala",   "sweet": 3, "salty": 3, "sour": 2, "bitter": 0, "umami": 4, "spice": 4 },
    { "dish_id": 4, "name": "Beef Pho",               "sweet": 2, "salty": 5, "sour": 2, "bitter": 0, "umami": 8, "spice": 1 },
    # …and so on for all your dishes…
]

dishes_df = pd.DataFrame(dish_list)
# extract the numeric columns for similarity
dish_vectors = dishes_df[["sweet", "salty", "sour", "bitter", "umami", "spice"]].values

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
# ===== NEW: Dishes table setup & seed =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS dishes (
  dish_id   SERIAL      PRIMARY KEY,
  name      TEXT        NOT NULL,
  sweet     SMALLINT    NOT NULL,
  salty     SMALLINT    NOT NULL,
  sour      SMALLINT    NOT NULL,
  bitter    SMALLINT    NOT NULL,
  umami     SMALLINT    NOT NULL,
  spice     SMALLINT    NOT NULL
);
""")
conn.commit()

# Seed it if empty
cursor.execute("SELECT COUNT(*) FROM dishes;")
if cursor.fetchone()[0] == 0:
    cursor.execute("""
    INSERT INTO dishes (name, sweet, salty, sour, bitter, umami, spice) VALUES
      ('Margherita Pizza',     2, 4, 1, 1, 5, 1),
      ('Tonkotsu Ramen',       1, 5, 1, 0, 9, 2),
      ('Pad Thai',             4, 4, 4, 0, 6, 3),
      ('Beef Pho',             2, 5, 2, 0, 8, 1),
      ('Chocolate Mousse',     5, 1, 0, 1, 2, 0),
      ('Guacamole',            1, 2, 3, 0, 3, 2),
      ('Miso Ramen',           1, 4, 1, 0, 9, 1),
      ('Chicken Tikka Masala', 3, 3, 2, 0, 7, 4),
      ('Beef Bulgogi',         4, 5, 1, 0, 7, 2),
      ('Falafel',              1, 3, 1, 0, 4, 2)
    ;
    """)
    conn.commit()
# ===== END NEW =====

@app.route('/debug/users', methods=['GET'])
def debug_list_users():
    """Returns every saved user and their preferences."""
    try:
        cursor.execute("SELECT user_id, preferences FROM users;")
        rows = cursor.fetchall()
        # rows is a list of tuples: [(user_id, prefs_json), …]
        users = [
            {
                "user_id": uid,
                "preferences": json.loads(prefs)
            }
            for uid, prefs in rows
        ]
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        # 1) Grab raw JSON
        payload = request.get_json()

        # 2) Unwrap Typeform payload, or use flat JSON
        if "form_response" in payload:
            fr = payload["form_response"]

            # hidden fields
            flat = fr.get("hidden", {}).copy()

            # custom URL vars
            for var in fr.get("variables", []):
                flat[var["key"]] = var.get("value")

            # question answers by ref
            for ans in fr.get("answers", []):
                ref = ans["field"]["ref"]
                if ans["type"] == "number":
                    flat[ref] = ans["number"]
                elif ans["type"] == "text":
                    flat[ref] = ans["text"]
                elif ans["type"] == "choice":
                    flat[ref] = ans["choice"]["label"]
        else:
            flat = payload

        # 3) Whitelist
        allowed = [
            "user_id",
            "sweet","sour","salty","bitter","umami",
            "textures","cuisines","spice_tolerance",
            "dietary_restrictions","allergies"
        ]

        data = {k: flat[k] for k in allowed if k in flat}

        # 4) Validate required
        flavor_map = { t: data[t] for t in ("sweet","sour","salty","bitter","umami") }

        save_user(
        data["user_id"],
        {
            "flavors": flavor_map,
            "textures": data.get("textures", []),
            "cuisines": data.get("cuisines", []),
            "spice_tolerance": data["spice_tolerance"],
            "dietary_restrictions": data.get("dietary_restrictions", []),
            "allergies": data.get("allergies", [])
        }
        )

        return jsonify({"status": "success", "user_id": data["user_id"]})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500




import traceback, sys

@app.route('/add_dish', methods=['POST'])
def add_dish():
    try:
        data = request.get_json()
        # Required fields
        required = [
            "user_id",
            "sweet","sour","salty","bitter","umami",
            "textures","cuisines","spice_tolerance"
        ]

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


from sklearn.metrics.pairwise import cosine_similarity

@app.route('/recommendations', methods=['GET'])
def recommendations():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error":"user_id is required"}), 400

        # 1) fetch user prefs
def load_dishes():
    cursor.execute("""
        SELECT name, sweet, salty, sour, bitter, umami, spice
        FROM dishes;
    """)
    rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=[
        "name", "sweet", "salty", "sour", "bitter", "umami", "spice"
    ])

# inside recommendations()
dishes_df = load_dishes()

        # 2) build user vector in the same order as dish_vectors
        user_vec = [
            prefs["flavors"].get("sweet", 0),
            prefs["flavors"].get("salty", 0),
            prefs["flavors"].get("sour", 0),
            prefs["flavors"].get("bitter", 0),
            prefs["flavors"].get("umami", 0),
            prefs.get("spice_tolerance", 0),
        ]

        # 3) compute similarities
        sims = cosine_similarity([user_vec], dish_vectors)[0]

        # 4) attach sims to DataFrame and pick top 5
        dishes_df["score"] = sims

        print(dishes_df[["name","score"]].sort_values("score", ascending=False).to_string(index=False))
        
        top5 = (
            dishes_df
            .sort_values("score", ascending=False)
            .head(5)[["name", "score"]]
            .to_dict(orient="records")
        )

        # round scores for readability
        for rec in top5:
            rec["score"] = round(rec["score"], 2)

        return jsonify(top5)


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