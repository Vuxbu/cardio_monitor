from garminconnect import Garmin
import datetime
import matplotlib.pyplot as plt

# update with your own credentials
username = "paulrafferty9@icloud.com"
password = "xxx"

# connect to the API
try:
  api = Garmin(username, password).login()
  print("✅ Garmin Connect login successful")
except Exception as e:
  print(f"An error occurred while initializing the API: {e}")
  
18945244896