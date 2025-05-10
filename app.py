import os
import json
import pandas as pd
import numpy as np
import psycopg2
import atexit

from flask import Flask, render_template, request, jsonify, abort
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()

def build_vector(record):
    """
    Turn the first 6 numeric fields + any arrays in `record` into a flat vector.
    For now we’ll just grab the first six flavor/spice values:
    """
    # record[0] = sweet, [1] = sour, [2] = salty, [3] = bitter,
    # [4] = umami, [5] = spice_tolerance
    vec = list(record[:6])
    return np.array(vec, dtype=float)

@app.route('/profile/<user_id>')
def profile(user_id):
    # 1) Load raw prefs JSON
    cur = conn.cursor()
    cur.execute(
        "SELECT preferences FROM users WHERE user_id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        abort(404)

    prefs = json.loads(row[0])

    # 2) Get the top-5 recs
    recs = get_recommendations(user_id)

    # 3) Render the profile page
    return render_template(
        'profile.html',
        title=f"Taste Profile for {user_id}",
        user_id=user_id,
        prefs=prefs,
        recs=recs
    )

# ← Paste get_recommendations right here ↓
def get_recommendations(user_id):
    """
    Returns up to 5 {dish_id, name, score} dicts,
    based only on the 6 numeric flavor/spice fields.
    """
    # 1) Load prefs JSON
    cur = conn.cursor()
    cur.execute(
        "SELECT preferences FROM users WHERE user_id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("User not found")
    prefs = json.loads(row[0])

    # Build a simple 6-value record for build_vector:
    record = [
        prefs["flavors"].get("sweet", 0),
        prefs["flavors"].get("sour",  0),
        prefs["flavors"].get("salty", 0),
        prefs["flavors"].get("bitter",0),
        prefs["flavors"].get("umami", 0),
        prefs.get("spice_tolerance", 0),
    ]
    user_vec = build_vector(record)

    # 2) Fetch only the six numeric columns from dishes
    df = pd.read_sql(
    """
    SELECT sweet, sour, salty, bitter, umami, spice, name, dish_id
    FROM dishes
    """,
    conn,
    )

    # 3) Vectorize & score
    dish_vecs = df.apply(
        lambda r: build_vector(r[['sweet','sour','salty','bitter','umami','spice']]),
        axis=1
    ).tolist()
    sims = cosine_similarity([user_vec], dish_vecs)[0]
    df["score"] = sims

    # 4) Dedupe by name & take top 5
    top5 = (
        df.sort_values("score", ascending=False)
          .groupby("name", as_index=False)
          .first()
          .nlargest(5, "score")
    )

    return top5[["dish_id","name","score"]].to_dict(orient="records")

# ← Now your existing routes, e.g. @app.route("/recommendations") …


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
        # now persist the transaction
        conn.commit()

        return jsonify({"status":"success","user_id": flat["user_id"]}), 200

    except Exception as e:
        conn.rollback() # clear out the failed transaction 
        return jsonify({"status":"error","message":str(e)}), 500



from sklearn.metrics.pairwise import cosine_similarity

@app.route("/recommendations")
def recommendations():
    user_id = request.args.get("user_id")
    try:
        recs = get_recommendations(user_id)
        return jsonify(recs)
    except ValueError:
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        app.logger.exception("rec failure")
        return jsonify({"error": str(e)}), 500

# ===== NEW: Cleanup handler =====
def close_db():
    conn.close()
atexit.register(close_db)
# ===== END NEW =====

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
