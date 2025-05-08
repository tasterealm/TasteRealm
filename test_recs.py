import requests

BASE = "https://tasterealmapi.onrender.com"

# 1) Submit the survey
survey_payload = {
    "user_id": "test_user_123",
    "flavors":     {"sweet":1, "sour":1, "salty":5, "bitter":0, "umami":8},
    "spice_tolerance": 2,
    "cuisines":    ["Vietnamese", "Japanese"],
    "textures":    ["chewy", "silky"],
    "dietary_restrictions": [],   # must be present
    "allergies":           []    # must be present
}
r = requests.post(f"{BASE}/submit_survey", json=survey_payload)
print("Survey response:", r.status_code, r.json())

# 2) Ask for recommendations
r2 = requests.get(f"{BASE}/recommendations", params={"user_id":"test_user_123"})
print("Top 5 dishes:", r2.status_code, r2.json())
