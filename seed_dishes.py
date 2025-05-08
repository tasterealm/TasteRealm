#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import execute_values

# ── 1) Your research-graded dish profiles
#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import execute_values

dishes = [
    {
      "name": "Margherita Pizza",
      "sweet": 2, "salty": 4, "sour": 1, "bitter": 1, "umami": 5, "spice": 1,
      "cuisine": ["Italian"],
      "textures": ["chewy","creamy"],
      "sensitive_ingredients": [],
      "dietary_restrictions": ["vegetarian"],
      "allergies": []
    },
    {
      "name": "Pad Thai",
      "sweet": 4, "salty": 4, "sour": 4, "bitter": 0, "umami": 6, "spice": 3,
      "cuisine": ["Thai"],
      "textures": ["chewy","crispy"],
      "sensitive_ingredients": ["peanuts"],
      "dietary_restrictions": [],
      "allergies": ["peanuts"]
    },
    {
      "name": "Beef Pho",
      "sweet": 2, "salty": 5, "sour": 2, "bitter": 0, "umami": 8, "spice": 1,
      "cuisine": ["Vietnamese"],
      "textures": ["slippery","tender"],
      "sensitive_ingredients": [],
      "dietary_restrictions": [],
      "allergies": []
    },
    {
      "name": "Guacamole",
      "sweet": 1, "salty": 2, "sour": 3, "bitter": 0, "umami": 2, "spice": 2,
      "cuisine": ["Mexican"],
      "textures": ["creamy","chunky"],
      "sensitive_ingredients": ["onion"],
      "dietary_restrictions": ["vegetarian","vegan","gluten-free"],
      "allergies": []
    },
    {
      "name": "Miso Ramen",
      "sweet": 1, "salty": 4, "sour": 0, "bitter": 0, "umami": 9, "spice": 2,
      "cuisine": ["Japanese"],
      "textures": ["chewy","silky"],
      "sensitive_ingredients": ["soy"],
      "dietary_restrictions": [],
      "allergies": ["soy"]
    },
    {
      "name": "Falafel",
      "sweet": 1, "salty": 3, "sour": 0, "bitter": 0, "umami": 3, "spice": 2,
      "cuisine": ["Middle Eastern"],
      "textures": ["crispy","grainy"],
      "sensitive_ingredients": [],
      "dietary_restrictions": ["vegetarian","vegan","gluten-free"],
      "allergies": []
    },
    {
      "name": "Tiramisu",
      "sweet": 4, "salty": 1, "sour": 0, "bitter": 1, "umami": 2, "spice": 0,
      "cuisine": ["Italian"],
      "textures": ["creamy","airy"],
      "sensitive_ingredients": ["coffee"],
      "dietary_restrictions": ["vegetarian"],
      "allergies": ["eggs","dairy"]
    },
    {
      "name": "Korean Fried Chicken",
      "sweet": 3, "salty": 5, "sour": 0, "bitter": 0, "umami": 5, "spice": 4,
      "cuisine": ["Korean"],
      "textures": ["crispy","juicy"],
      "sensitive_ingredients": [],
      "dietary_restrictions": [],
      "allergies": []
    },
    {
      "name": "Shakshuka",
      "sweet": 1, "salty": 3, "sour": 2, "bitter": 0, "umami": 4, "spice": 2,
      "cuisine": ["Middle Eastern"],
      "textures": ["soupy","creamy"],
      "sensitive_ingredients": ["onion","garlic"],
      "dietary_restrictions": ["vegetarian","vegan","gluten-free"],
      "allergies": []
    },
    {
      "name": "Chicken Tikka Masala",
      "sweet": 3, "salty": 2, "sour": 1, "bitter": 0, "umami": 7, "spice": 4,
      "cuisine": ["Indian"],
      "textures": ["tender","creamy"],
      "sensitive_ingredients": ["onion","garlic"],
      "dietary_restrictions": [],
      "allergies": []
    },
]

# ── rest of your seed_dishes.py follows unchanged ──
# connect, drop/create table, execute_values, commit, print count…


# ── 2) Connect & drop/recreate the table
DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS dishes;")
cur.execute("""
CREATE TABLE dishes (
  dish_id               SERIAL      PRIMARY KEY,
  name                  TEXT        NOT NULL,
  sweet                 SMALLINT    NOT NULL,
  sour                  SMALLINT    NOT NULL,
  salty                 SMALLINT    NOT NULL,
  bitter                SMALLINT    NOT NULL,
  umami                 SMALLINT    NOT NULL,
  spice                 SMALLINT    NOT NULL,
  cuisine              TEXT[]      NOT NULL,
  textures              TEXT[]      NOT NULL,
  sensitive_ingredients TEXT[]      NOT NULL,
  dietary_restrictions  TEXT[]      NOT NULL,
  allergies             TEXT[]      NOT NULL
);
""")
conn.commit()

# ── 3) Bulk‐insert all of them
sql = """
  INSERT INTO dishes
    (name, sweet, sour, salty, bitter, umami, spice,
     cuisine, textures, sensitive_ingredients,
     dietary_restrictions, allergies)
  VALUES %s
  RETURNING dish_id;
"""

values = [
  (
    d["name"],
    d["sweet"], d["sour"], d["salty"], d["bitter"],
    d["umami"], d["spice"],
    d["cuisine"], d["textures"],
    d["sensitive_ingredients"],
    d["dietary_restrictions"],
    d["allergies"]
  )
  for d in dishes
]

execute_values(cur, sql, values)
conn.commit()
print(f"✅ Seeded {len(dishes)} dishes.")
cur.close()
conn.close()
