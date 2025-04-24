import pandas as pd

# Load the datasets
dish_profiles = pd.read_csv("C:\\Users\\Omar\\Documents\\Dish Profiles Sample.csv")
user_profiles = pd.read_csv("C:\\Users\\Omar\\Documents\\User Profiles Sample.csv")

# Display the first few rows of each dataset
print("Dish Profiles:")
print(dish_profiles.head())

print("\nUser Profiles:")
print(user_profiles.head())