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
# near the top of app.py, after you open `conn` and `cursor`...


@app.route("/add_dish", methods=["POST"])
def add_dish():
    """
    Expects JSON with:
      name, sweet, sour, salty, bitter, umami, spice,
      cuisines,
      textures,           # list of strings
      dietary_restrictions,  # list of strings
      allergies           # list of strings
    """
    data = request.get_json()
    required = [
      "name", "sweet", "sour", "salty", "bitter", "umami", "spice",
      "cuisines",
      "textures", "dietary_restrictions", "allergies"
    ]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing field: {f}"}), 400

    cursor.execute("""
      INSERT INTO dishes (
        name, sweet, sour, salty, bitter, umami, spice,
        cuisines,
        textures, sensitive_ingredients, dietary_restrictions, allergies
      ) VALUES (
        %s, %s, %s, %s, %s, %s, %s,
        %s,
        %s, %s, %s, %s
      ) RETURNING dish_id;
    """, (
      data["name"],
      data["sweet"],
      data["sour"],
      data["salty"],
      data["bitter"],
      data["umami"],
      data["spice"],
      data["cuisines"],
      data["textures"],
      data["sensitive_ingredients"],
      data["dietary_restrictions"],
      data["allergies"],
    ))
    new_id = cursor.fetchone()[0]
    conn.commit()
    return jsonify({"status":"added","dish_id":new_id}), 201

@app.route('/dishes', methods=['GET'])
def list_dishes():
    df = load_dishes()
    return jsonify(df.to_dict(orient='records'))


# ── helper to load all dishes from Postgres ────────────────
def load_dishes():
    """Fetch all dishes from Postgres and return a DataFrame."""
    cursor.execute("""
      SELECT
        name, sweet, sour, salty, bitter, umami, spice,
        cuisines, textures, sensitive_ingredients,
        dietary_restrictions, allergies
      FROM dishes;
    """)
    rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=[
      "name", "sweet", "sour", "salty", "bitter", "umami", "spice",
      "cuisines", "textures", "sensitive_ingredients",
      "dietary_restrictions", "allergies"
    ])



cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        preferences TEXT
    );
""")
conn.commit()


# ── 2) Seed the dishes table if empty ────────────────────────────
cursor.execute("SELECT COUNT(*) FROM dishes;")
if cursor.fetchone()[0] == 0:
    cursor.execute("""
    INSERT INTO dishes (
      name,
      sweet, sour, salty, bitter, umami, spice,
      cuisines,
      textures,
      sensitive_ingredients,
      dietary_restrictions,
      allergies
    ) VALUES
      (
        'Margherita Pizza',
         2,    1,      4,      1,      5,      1,
        ARRAY['Italian'],
        ARRAY['chewy','creamy'],
        ARRAY[]::TEXT[],            -- no highly-sensitive ingredients
        ARRAY['vegetarian'],
        ARRAY[]::TEXT[]             -- no expected allergies
      ),
      (
        'Pad Thai',
         4,    4,      4,      0,      6,      3,
        ARRAY['Thai'],
        ARRAY['chewy','crispy'],
        ARRAY[]::TEXT[],
        ARRAY[]::TEXT[],
        ARRAY[]::TEXT[]
      ),
      (
        'Chicken Tikka Masala',
         3,    2,      3,      0,      7,      4,
        ARRAY['Indian'],
        ARRAY['tender','creamy'],
        ARRAY['onion','garlic'],    -- typical aromatics
        ARRAY[]::TEXT[],
        ARRAY[]::TEXT[]
      ),
      (
        'Beef Pho',
         2,    2,      5,      0,      8,      1,
        ARRAY['Vietnamese'],
        ARRAY['slippery','tender'],
        ARRAY[]::TEXT[],
        ARRAY[]::TEXT[],
        ARRAY[]::TEXT[]
      ),
      (
        'Chocolate Mousse',
         5,    0,      1,      1,      2,      0,
        ARRAY['French'],
        ARRAY['airy','creamy'],
        ARRAY[]::TEXT[],
        ARRAY['vegetarian'],
        ARRAY[]::TEXT[]
      ),
      (
        'Guacamole',
         1,    3,      2,      0,      3,      2,
        ARRAY['Mexican'],
        ARRAY['creamy','chunky'],
        ARRAY['onion'],             -- some dislike raw onion
        ARRAY['vegetarian','vegan'],
        ARRAY[]::TEXT[]
      );
    """)
    conn.commit()
# ── END SEED ─────────────────────────────────────────────────────

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
        payload = request.get_json()

        # 1) Unwrap Typeform or take flat JSON
        if "form_response" in payload:
            fr = payload["form_response"]
            flat = fr.get("hidden", {}).copy()
            for var in fr.get("variables", []):
                flat[var["key"]] = var.get("value")
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

        # 2) Pull out flavors (nested) or fallback to flat keys
        if "flavors" in flat and isinstance(flat["flavors"], dict):
            flavor_map = flat["flavors"]
        else:
            # support legacy flat keys if someone used them
            flavor_map = {
                k: flat.get(k, 0)
                for k in ("sweet","sour","salty","bitter","umami")
            }

        # 3) Pull out plural cuisines, textures, dietary, allergies
        cuisines = flat.get("cuisines", flat.get("cuisines", []))
        textures = flat.get("textures", [])
        dietary = flat.get("dietary_restrictions", [])
        allergies = flat.get("allergies", [])
        spice_tol = flat.get("spice_tolerance") or flat.get("spice", 0)

        # 4) Validate required
        missing = []
        if "user_id" not in flat: missing.append("user_id")
        if spice_tol is None:       missing.append("spice_tolerance")
        if not flavor_map:         missing.append("flavors")
        if missing:
            return jsonify({
                "status":"error",
                "message": f"Missing field(s): {', '.join(missing)}"
            }), 400

        # 5) Save into Postgres
        save_user(
            flat["user_id"],
            {
                "flavors": flavor_map,
                "textures": textures,
                "cuisines": cuisines,
                "spice_tolerance": spice_tol,
                "dietary_restrictions": dietary,
                "allergies": allergies
            }
        )
        return jsonify({"status":"success","user_id":flat["user_id"]}), 200

    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500



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