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
conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")
cursor = conn.cursor()
# near the top of app.py, after you open `conn` and `cursor`...

def build_vector(record):
    """
    Given a tuple of (sweet, sour, salty, bitter, umami, spice, textures, cuisines, sensitive_ingredients, dietary_restrictions, allergies),
    return a flat numeric vector (e.g. flavor scales + one-hot arrays for the list-columns).
    You can reuse your existing helper logic here.
    """
    # … your code to turn record into a 1D array …
    pass


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
        conn.rollback() # clear out the failed transaction 
        return jsonify({"status":"error","message":str(e)}), 500



from sklearn.metrics.pairwise import cosine_similarity

@app.route("/recommendations")
def recommendations():
    user_id = request.args.get("user_id")
    cur = conn.cursor()
    # 1) Fetch the user’s taste profile
    cur.execute(
        """
        SELECT sweet, sour, salty, bitter, umami, spice,
               textures, cuisines, sensitive_ingredients,
               dietary_restrictions, allergies
        FROM users
        WHERE user_id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "User not found"}), 404

    user_vec = build_vector(row)

    # 2) Pull every dish from Postgres
    df = pd.read_sql(
        """
        SELECT dish_id, name,
               sweet, sour, salty, bitter, umami, spice,
               textures, cuisines, sensitive_ingredients,
               dietary_restrictions, allergies
        FROM dishes
        """,
        conn,
    )

    # 3) Build dish vectors
    dish_vecs = df.apply(
        lambda r: build_vector(r[["sweet","sour","salty","bitter","umami","spice",
                                  "textures","cuisines","sensitive_ingredients",
                                  "dietary_restrictions","allergies"]]), axis=1
    ).tolist()

    # 4) Compute cosine similarities
    sims = cosine_similarity([user_vec], dish_vecs)[0]

    # 5) Attach scores and sort
    df["score"] = sims
    df_sorted = df.sort_values("score", ascending=False)

    # 6) Take the top 5 unique dishes
    top_five = df_sorted.drop_duplicates(subset="dish_id").head(5)

    # 7) Return JSON
    results = top_five[["dish_id","name","score"]].to_dict(orient="records")
    return jsonify(results)


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