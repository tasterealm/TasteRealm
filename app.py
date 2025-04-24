from flask import Flask, request, jsonify
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3  # <-- NEW: Database import
import json     # <-- NEW: For JSON handling
import atexit   # <-- NEW: For cleanup

app = Flask(__name__)

@app.route('/')
def home():
    return "TasteRealm API is running! Endpoints: /submit_survey (POST) and /recommendations (GET)"

# ===== NEW: SQLite Database Setup =====
conn = sqlite3.connect('tasterealm.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id TEXT PRIMARY KEY, preferences TEXT)''')
conn.commit()

def save_user(user_id, data):
    """Save user preferences to SQLite"""
    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?)",
        (user_id, json.dumps(data))
    )
    conn.commit()

def get_user(user_id):
    """Retrieve user preferences from SQLite"""
    cursor.execute("SELECT preferences FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result else None
# ===== END NEW =====

dishes = pd.DataFrame([
    # Original dishes (kept for reference)
    {"dish_id": 1, "name": "Margherita Pizza", "sweet": 2, "umami": 5, "textures": ["chewy", "creamy"], "cuisine": "Italian", "spice": 1, "dietary_restrictions": ["vegetarian"]},
    {"dish_id": 2, "name": "Chocolate Mousse", "sweet": 5, "umami": 1, "textures": ["creamy", "fluffy"], "cuisine": "French", "spice": 1, "dietary_restrictions": ["vegetarian"]},
    {"dish_id": 3, "name": "Chicken Tikka Masala", "sweet": 3, "umami": 4, "textures": ["tender", "creamy"], "cuisine": "Indian", "spice": 3, "dietary_restrictions": []},

    # New dishes (vetted with culinary sources)
    {"dish_id": 4, "name": "Beef Pho", "sweet": 2, "umami": 8, "textures": ["slippery", "tender"], "cuisine": "Vietnamese", "spice": 1, "dietary_restrictions": []},  # Broth umami from star anise + beef bones
    {"dish_id": 5, "name": "Guacamole", "sweet": 1, "umami": 2, "textures": ["creamy", "chunky"], "cuisine": "Mexican", "spice": 2, "dietary_restrictions": ["vegetarian", "vegan"]},  # Lime adds brightness
    {"dish_id": 6, "name": "Miso Ramen", "sweet": 1, "umami": 9, "textures": ["chewy", "silky"], "cuisine": "Japanese", "spice": 2, "dietary_restrictions": []},  # Miso = umami powerhouse
    {"dish_id": 7, "name": "Pad Thai", "sweet": 3, "umami": 4, "textures": ["chewy", "crispy"], "cuisine": "Thai", "spice": 2, "dietary_restrictions": []},  # Tamarind adds sweet-sour
    {"dish_id": 8, "name": "Falafel", "sweet": 1, "umami": 3, "textures": ["crispy", "grainy"], "cuisine": "Middle Eastern", "spice": 2, "dietary_restrictions": ["vegetarian", "vegan"]},  # Chickpea base
    {"dish_id": 9, "name": "Tiramisu", "sweet": 4, "umami": 2, "textures": ["creamy", "airy"], "cuisine": "Italian", "spice": 1, "dietary_restrictions": ["vegetarian"]},  # Coffee-soaked layers
    {"dish_id": 10, "name": "Korean Fried Chicken", "sweet": 3, "umami": 5, "textures": ["crispy", "juicy"], "cuisine": "Korean", "spice": 4, "dietary_restrictions": []},  # Gochujang glaze
    {"dish_id": 11, "name": "Caprese Salad", "sweet": 2, "umami": 4, "textures": ["juicy", "creamy"], "cuisine": "Italian", "spice": 1, "dietary_restrictions": ["vegetarian"]},  # Fresh mozz + tomatoes
    {"dish_id": 12, "name": "Beef Bulgogi", "sweet": 4, "umami": 6, "textures": ["tender", "juicy"], "cuisine": "Korean", "spice": 2, "dietary_restrictions": []}  # Pear-marinated
])


@app.route('/submit_survey', methods=['POST'])
def submit_survey():
    """Endpoint to store user survey responses"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['user_id', 'flavors', 'textures', 'cuisines', 'spice_tolerance']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing field: {field}"}), 400

        # ===== CHANGED: Now using SQLite instead of mock dictionary =====
        save_user(data['user_id'], {
            "flavors": data['flavors'],
            "textures": data['textures'],
            "cuisines": data['cuisines'],
            "spice_tolerance": data['spice_tolerance'],
            "dietary_restrictions": data.get('dietary_restrictions', []),
            "allergies": data.get('allergies', [])
        })
        # ===== END CHANGED =====

        return jsonify({"status": "success", "user_id": data['user_id']})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/recommendations', methods=['GET'])
def get_recommendations():
    """Endpoint to generate personalized dish recommendations"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        user = get_user(user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Prepare user vector
        user_vector = [
            user['flavors'].get('sweet', 0),
            user['flavors'].get('umami', 0),
            user['spice_tolerance']
        ]

        # Prepare dish vectors
        dish_vectors = dishes[['sweet', 'umami', 'spice']].values

        # Calculate cosine similarity
        similarity_scores = cosine_similarity([user_vector], dish_vectors)[0]
        dishes['similarity_score'] = similarity_scores

        # Filter based on preferences
        recommended = dishes[
            (dishes['cuisine'].isin(user['cuisines'])) &
            (dishes['spice'] <= user['spice_tolerance']) &
            (dishes['textures'].apply(lambda x: any(t in x for t in user['textures'])))
        ].sort_values('similarity_score', ascending=False)

        # Format results (THIS IS THE CRITICAL PART - PROPER INDENTATION)
        results = [{
            "dish_id": dish["dish_id"],
            "name": dish["name"],
            "cuisine": dish["cuisine"],
            "umami": dish["umami"],
            "sweet": dish["sweet"],
            "textures": dish["textures"],
            "spice": dish["spice"],
            "dietary_restrictions": dish["dietary_restrictions"],
            "similarity_score": round(float(dish["similarity_score"]), 2)
        } for dish in recommended.head(5).to_dict(orient='records')]

        return jsonify({"status": "success", "recommendations": results})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== NEW: Cleanup handler =====
def close_db():
    conn.close()
atexit.register(close_db)
# ===== END NEW =====

if __name__ == '__main__':
    app.run(debug=True, port=5000)