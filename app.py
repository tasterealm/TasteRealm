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



# ── FORCE MIGRATION: drop old dishes table so our new schema applies ──
cursor.execute("DROP TABLE IF EXISTS dishes;")

# ── 1) create a dishes table that matches your 8 survey questions ──
cursor.execute("""
CREATE TABLE IF NOT EXISTS dishes (
  dish_id               SERIAL      PRIMARY KEY,
  name                  TEXT        NOT NULL,
  sweet                 SMALLINT    NOT NULL,    -- 1–5
  sour                  SMALLINT    NOT NULL,    -- 1–5
  salty                 SMALLINT    NOT NULL,    -- 1–5
  bitter                SMALLINT    NOT NULL,    -- 1–5
  umami                 SMALLINT    NOT NULL,    -- 1–5
  spice                 SMALLINT    NOT NULL,    -- 1–5

  cuisine              TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],  -- Q7
  textures              TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],  -- Q8
  sensitive_ingredients TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],  -- Q9
  dietary_restrictions  TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],  -- Q10
  allergies             TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[]   -- Q11
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
      allergies           # list of strings
    """
    data = request.get_json()
    required = [
      "name", "sweet", "sour", "salty", "bitter", "umami", "spice",
      "cuisine",
      "textures", "dietary_restrictions", "allergies"
    ]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing field: {f}"}), 400

    cursor.execute("""
      INSERT INTO dishes (
        name, sweet, sour, salty, bitter, umami, spice,
        cuisine,
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
      data["cuisine"],
      data["textures"],
      data["sensitive_ingredients"],
      data["dietary_restrictions"],
      data["allergies"],
    ))
    new_id = cursor.fetchone()[0]
    conn.commit()
    return jsonify({"status":"added","dish_id":new_id}), 201


# ── helper to load all dishes from Postgres ────────────────
def load_dishes():
    """Fetch all dishes from Postgres and return a DataFrame."""
    cursor.execute("""
      SELECT
        name, sweet, sour, salty, bitter, umami, spice,
        cuisine, textures, sensitive_ingredients,
        dietary_restrictions, allergies
      FROM dishes;
    """)
    rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=[
      "name", "sweet", "sour", "salty", "bitter", "umami", "spice",
      "cuisine", "textures", "sensitive_ingredients",
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
      cuisine,
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
            "textures","cuisine","spice_tolerance",
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
            "cuisine": data.get("cuisine", []),
            "spice_tolerance": data["spice_tolerance"],
            "dietary_restrictions": data.get("dietary_restrictions", []),
            "allergies": data.get("allergies", [])
        }
        )

        return jsonify({"status": "success", "user_id": data["user_id"]})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500






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