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


app = Flask(__name__)

@app.route('/')
def home():
    return "TasteRealm API is running! Endpoints: /submit_survey (POST) and /recommendations (GET)"

# ===== NEW: SQLite Database Setup =====
DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()
# near the top of app.py, after you open `conn` and `cursor`...

# --- FORCE MIGRATION: drop old dishes table so our new schema applies ---
cursor.execute("DROP TABLE IF EXISTS dishes;")
# --- CREATE dishes table with all your extended columns ---
cursor.execute("""
CREATE TABLE dishes (
  dish_id               SERIAL       PRIMARY KEY,
  name                  TEXT         NOT NULL,
  sweet                 SMALLINT     NOT NULL,
  salty                 SMALLINT     NOT NULL,
  sour                  SMALLINT     NOT NULL,
  bitter                SMALLINT     NOT NULL,
  umami                 SMALLINT     NOT NULL,
  spice                 SMALLINT     NOT NULL,
  cuisine               TEXT        NOT NULL,
  textures              TEXT[]      NOT NULL,
  dietary_restrictions  TEXT[]      NOT NULL,
  allergens             TEXT[]      NOT NULL
);
""")
conn.commit()

@app.route("/add_dish", methods=["POST"])
def add_dish():
    """
    Expects JSON with:
      name, sweet, sour, salty, bitter, umami, spice,
      cuisine,
      textures,           # list of strings
      dietary_restrictions,  # list of strings
      allergens           # list of strings
    """
    data = request.get_json()
    required = [
      "name", "sweet", "sour", "salty", "bitter", "umami", "spice",
      "cuisine",
      "textures", "dietary_restrictions", "allergens"
    ]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing field: {f}"}), 400

    cursor.execute("""
      INSERT INTO dishes (
        name, sweet, sour, salty, bitter, umami, spice,
        cuisine,
        textures, dietary_restrictions, allergens
      ) VALUES (
        %s, %s, %s, %s, %s, %s, %s,
        %s,
        %s, %s, %s
      ) RETURNING dish_id;
    """, (
      data["name"],
      data["sweet"],
      data["sour"],
      data["salty"],
      data["bitter"],
      data["umami"],
      data["spice"],
      data["cuisine"],
      data["textures"],
      data["dietary_restrictions"],
      data["allergens"],
    ))
    new_id = cursor.fetchone()[0]
    conn.commit()
    return jsonify({"status":"added","dish_id":new_id}), 201


# ── helper to load all dishes from Postgres ────────────────
def load_dishes():
    """Fetch all dishes from Postgres and return a DataFrame."""
    cursor.execute("""
      SELECT
        name, sweet, salty, sour, bitter, umami, spice,
        textures, cuisine, dietary_restrictions, allergy_risk,
        protein_sources, prep_method, portion_fill,
        temperature, ethics_rating, presentation_rating,
        origin_region, foreignness, healthiness_rating
      FROM dishes;
    """)
    rows = cursor.fetchall()
    cols = [
      "name","sweet","salty","sour","bitter","umami","spice",
      "textures","cuisine","dietary_restrictions","allergy_risk",
      "protein_sources","prep_method","portion_fill",
      "temperature","ethics_rating","presentation_rating",
      "origin_region","foreignness","healthiness_rating"
    ]
    return pd.DataFrame(rows, columns=cols)


cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        preferences TEXT
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
        cursor.execute(
            "SELECT preferences FROM users WHERE user_id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error":"User not found"}), 404
        prefs = json.loads(row[0])

        # 2) pull in your full dish list
        dishes_df = load_dishes()

        # 3) build user taste vector
        user_vec = [
            prefs["flavors"].get("sweet", 0),
            prefs["flavors"].get("salty", 0),
            prefs["flavors"].get("sour",  0),
            prefs["flavors"].get("bitter",0),
            prefs["flavors"].get("umami", 0),
            prefs.get("spice_tolerance", 0),
        ]

        # 4) cosine similarity & top 5
        sims = cosine_similarity(
            [user_vec],
            dishes_df[["sweet","salty","sour","bitter","umami","spice"]]
        )[0]
        dishes_df["score"] = sims
        top5 = (
            dishes_df
            .sort_values("score", ascending=False)
            .head(5)[["name","score"]]
            .to_dict(orient="records")
        )

        # 5) round scores for readability
        for rec in top5:
            rec["score"] = round(rec["score"], 2)

        return jsonify(top5)

    except Exception as e:
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