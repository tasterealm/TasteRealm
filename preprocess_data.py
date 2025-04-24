import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# Load the datasets
user_profiles = pd.read_excel(r"C:\Users\Omar\Desktop\TasteRealm\User Profiles.xlsx")
dish_profiles = pd.read_excel(r"C:\Users\Omar\Desktop\TasteRealm\Dish Profiles.xlsx")

# Drop the 'Skill Level Required' column from dish_profiles
dish_profiles = dish_profiles.drop(columns=['Skill Level Required'], errors='ignore')

# Fill missing 'Sweet Preference' with the mean
user_profiles['Sweet Preference'] = user_profiles['Sweet Preference'].fillna(user_profiles['Sweet Preference'].mean())

# Save the cleaned data back to Excel
user_profiles.to_excel("User Profiles_Cleaned.xlsx", index=False)
dish_profiles.to_excel("Dish Profiles_Cleaned.xlsx", index=False)

# Load cleaned datasets
user_profiles = pd.read_excel("User Profiles_Cleaned.xlsx")
dish_profiles = pd.read_excel("Dish Profiles_Cleaned.xlsx")

# Drop the 'Skill Level Required' column again (if it reappears)
dish_profiles = dish_profiles.drop(columns=['Skill Level Required'], errors='ignore')

# Normalize user preferences (scale 0 to 1)
user_profiles_normalized = user_profiles.iloc[:, 1:].apply(lambda x: x / 10)

# Normalize dish attributes (scale 0 to 1)
dish_profiles_normalized = dish_profiles.iloc[:, 1:].apply(lambda x: x / 10)

# Check for missing values
print("Missing values in user_profiles_normalized:")
print(user_profiles_normalized.isnull().sum())

print("Missing values in dish_profiles_normalized:")
print(dish_profiles_normalized.isnull().sum())

# Fill missing values with 0
user_profiles_normalized = user_profiles_normalized.fillna(0)
dish_profiles_normalized = dish_profiles_normalized.fillna(0)

# Ensure both datasets have the same columns
common_columns = user_profiles_normalized.columns.intersection(dish_profiles_normalized.columns)
user_profiles_normalized = user_profiles_normalized[common_columns]
dish_profiles_normalized = dish_profiles_normalized[common_columns]

# Save normalized data (optional)
user_profiles_normalized.to_excel("User Profiles_Normalized.xlsx", index=False)
dish_profiles_normalized.to_excel("Dish Profiles_Normalized.xlsx", index=False)

# Calculate cosine similarity
similarity_matrix = cosine_similarity(user_profiles_normalized, dish_profiles_normalized)

# Create a DataFrame for similarity scores
similarity_df = pd.DataFrame(similarity_matrix, index=user_profiles['Name'], columns=dish_profiles['Dish'])

# Save similarity scores to Excel
similarity_df.to_excel("Similarity_Scores.xlsx")

print("Similarity scores calculated and saved to 'Similarity_Scores.xlsx'.")

# Load similarity scores
similarity_df = pd.read_excel("Similarity_Scores.xlsx", index_col=0)

# Check for duplicate rows
duplicates = similarity_df[similarity_df.index.duplicated(keep=False)]
print("Duplicate rows:")
print(duplicates)

# Drop duplicate rows (keep the first occurrence)
similarity_df = similarity_df[~similarity_df.index.duplicated(keep='first')]

# Debug: Check the structure of similarity_df
print("Similarity DataFrame:")
print(similarity_df.head())

# Debug: Check the first user's recommendations
first_user = similarity_df.index[0]
print(f"First user: {first_user}")
print(f"First user's recommendations:")
print(similarity_df.loc[first_user])

# Function to get top recommendations for a user
def get_top_recommendations(user_name, top_n=3):
    # Ensure the output is a Series (not DataFrame)
    user_scores = similarity_df.loc[user_name]
    if isinstance(user_scores, pd.DataFrame):
        # If multiple rows exist for the user, take the first one
        user_scores = user_scores.iloc[0]
    
    # Sort and get top N recommendations
    top_recommendations = user_scores.sort_values(ascending=False).head(top_n)
    return top_recommendations


# Generate recommendations for all users
recommendations = []
for user in similarity_df.index:
    top_recommendations = get_top_recommendations(user, top_n=3)
    for dish, score in top_recommendations.items():
        recommendations.append({
            'User': user,
            'Dish': dish,
            'Similarity Score': score
        })

# Convert recommendations to a DataFrame
recommendations_df = pd.DataFrame(recommendations)

# Save recommendations to Excel
recommendations_df.to_excel("User_Recommendations.xlsx", index=False)

print("Recommendations saved to 'User_Recommendations.xlsx'.")