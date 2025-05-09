# seed_dishes.py

import os
import psycopg2
import json

# 1) Connect
DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cur = conn.cursor()

# 2) (Re)create the dishes table
cur.execute("""
CREATE TABLE IF NOT EXISTS dishes (
    dish_id SERIAL PRIMARY KEY,
    name TEXT,
    sweet INTEGER,
    salty INTEGER,
    sour INTEGER,
    bitter INTEGER,
    umami INTEGER,
    spice INTEGER,
    cuisines TEXT[],
    textures TEXT[],
    sensitive_ingredients TEXT[],
    dietary_restrictions TEXT[],
    allergies TEXT[]
);
""")
conn.commit()

# 3) Define 10 dishes
dishes = [
    {
        "name": "Margherita Pizza",
        "sweet": 2, "salty": 4, "sour": 1, "bitter": 1, "umami": 5, "spice": 1,
        "cuisines": ["Italian"],
        "textures": ["chewy", "creamy"],
        "sensitive_ingredients": [],
        "dietary_restrictions": ["vegetarian"],
        "allergies": []
    },
    {
        "name": "Beef Pho",
        "sweet": 2, "salty": 5, "sour": 2, "bitter": 0, "umami": 8, "spice": 1,
        "cuisines": ["Vietnamese"],
        "textures": ["brothy", "tender"],
        "sensitive_ingredients": [],
        "dietary_restrictions": [],
        "allergies": ["beef"]
    },
    {
        "name": "Guacamole",
        "sweet": 1, "salty": 2, "sour": 3, "bitter": 0, "umami": 2, "spice": 2,
        "cuisines": ["Mexican"],
        "textures": ["creamy", "chunky"],
        "sensitive_ingredients": [],
        "dietary_restrictions": ["vegetarian", "vegan", "gluten-free"],
        "allergies": ["avocado"]
    },
    {
        "name": "Miso Ramen",
        "sweet": 1, "salty": 4, "sour": 0, "bitter": 1, "umami": 9, "spice": 2,
        "cuisines": ["Japanese"],
        "textures": ["chewy", "silky"],
        "sensitive_ingredients": ["soy"],
        "dietary_restrictions": [],
        "allergies": ["soy"]
    },
    {
        "name": "Pad Thai",
        "sweet": 3, "salty": 4, "sour": 4, "bitter": 0, "umami": 6, "spice": 3,
        "cuisines": ["Thai"],
        "textures": ["chewy", "crispy"],
        "sensitive_ingredients": ["peanuts", "fish sauce"],
        "dietary_restrictions": ["gluten-free"],
        "allergies": ["peanuts", "shellfish"]
    },
    {
        "name": "Falafel",
        "sweet": 1, "salty": 3, "sour": 0, "bitter": 0, "umami": 3, "spice": 2,
        "cuisines": ["Middle Eastern"],
        "textures": ["crispy", "grainy"],
        "sensitive_ingredients": [],
        "dietary_restrictions": ["vegetarian", "vegan"],
        "allergies": ["legumes"]
    },
    {
        "name": "Tiramisu",
        "sweet": 5, "salty": 1, "sour": 0, "bitter": 1, "umami": 2, "spice": 0,
        "cuisines": ["Italian"],
        "textures": ["creamy", "airy"],
        "sensitive_ingredients": ["coffee", "egg"],
        "dietary_restrictions": ["vegetarian"],
        "allergies": ["egg", "dairy"]
    },
    {
        "name": "Korean Fried Chicken",
        "sweet": 3, "salty": 5, "sour": 0, "bitter": 0, "umami": 5, "spice": 4,
        "cuisines": ["Korean"],
        "textures": ["crispy", "juicy"],
        "sensitive_ingredients": ["soy"],
        "dietary_restrictions": [],
        "allergies": ["soy"]
    },
    {
        "name": "Caprese Salad",
        "sweet": 2, "salty": 3, "sour": 1, "bitter": 0, "umami": 4, "spice": 0,
        "cuisines": ["Italian"],
        "textures": ["juicy", "creamy"],
        "sensitive_ingredients": [],
        "dietary_restrictions": ["vegetarian", "gluten-free"],
        "allergies": ["dairy"]
    },
    {
        "name": "Beef Bulgogi",
        "sweet": 4, "salty": 5, "sour": 1, "bitter": 0, "umami": 6, "spice": 2,
        "cuisines": ["Korean"],
        "textures": ["tender", "juicy"],
        "sensitive_ingredients": ["soy"],
        "dietary_restrictions": [],
        "allergies": ["soy"]
    }
]

# 4) Insert them all in one go
args_str = ",".join(
    cur.mogrify(
        "(" + ",".join(["%s"] * 12) + ")",
        (
            d["name"],
            d["sweet"], d["salty"], d["sour"], d["bitter"], d["umami"], d["spice"],
            d["cuisines"], d["textures"],
            d["sensitive_ingredients"], d["dietary_restrictions"], d["allergies"]
        )
    ).decode("utf-8")
    for d in dishes
)

cur.execute(
    f"INSERT INTO dishes (name, sweet, salty, sour, bitter, umami, spice, cuisines, textures, sensitive_ingredients, dietary_restrictions, allergies) VALUES {args_str};"
)
conn.commit()

print(f"✅ Seeded {len(dishes)} dishes.")
cur.close()
conn.close()
