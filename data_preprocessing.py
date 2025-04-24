import pandas as pd

# Load the data
users = pd.read_csv('User Profiles Sample.csv')
dishes = pd.read_csv('Dish Profiles Sample.csv')

# Normalize ratings columns to be between 0 and 1
dish_rating_columns = [
    'Sweet', 'Sour', 'Salty', 'Bitter', 'Umami', 'Spiciness', 
    'Budget Rating', 'Allergy Rating', 'Dietary Restrictions Rating', 
    'Protein Rating', 'Sensitive Ingredients Rating', 'Cuisine Rating', 
    'Innovation', 'Freshness', 'Portion Size', 'Ethical Rating', 
    'Popularity Rating', 'Nutritional Value', 'Environmental Impact'
]

user_rating_columns = [
    'Sweet Preference', 'Sour Preference', 'Salty Preference', 
    'Bitter Preference', 'Umami Preference', 'Spiciness Preference', 
    'Minimum Budget', 'Maximum Budget', 'Budget Preference', 
    'Allergy Severity', 'Dietary Restrictions Strictness', 
    'Protein Preference', 'Sensitive Ingredients Rating', 
    'Innovation', 'Freshness Importance', 'Portion Size Preference', 
    'Ethics Importance'
]

for column in dish_rating_columns:
    dishes[column] = dishes[column] / 10

for user_column in user_rating_columns:
    users[user_column] = users[user_column] / 10

# Handle missing values by filling them with the mean of the column
numeric_dish_columns = dishes.select_dtypes(include=['float64', 'int64']).columns
numeric_user_columns = users.select_dtypes(include=['float64', 'int64']).columns

dishes[numeric_dish_columns] = dishes[numeric_dish_columns].fillna(dishes[numeric_dish_columns].mean())
users[numeric_user_columns] = users[numeric_user_columns].fillna(users[numeric_user_columns].mean())


# One-hot encode categorical columns
categorical_columns = [
    'Preparation Method', 'Temperature', 'Ethical Sourcing', 
    'Seasonality', 'Preparation Time', 'Skill Level Required', 
    'Allergy Identifier', 'Dietary Restrictions Identifier', 
    'Sensitive Ingredients Identifier', 'Cuisine Preference Identifier'
]
dishes = pd.get_dummies(dishes, columns=categorical_columns)
users = pd.get_dummies(users, columns=categorical_columns)

print("Data preprocessing completed!")
