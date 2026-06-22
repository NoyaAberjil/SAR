from Raspberry_Code.logger import logger
from Raspberry_Code.mavlink import *
from collections import deque # FIX 1: Import deque instead of queue
import time
MAV_COM="/dev/ttyACM0"
# MAV_COM="/dev/serial0" 
#MAV_COM="tcp:localhost:5763" # SITL com
MAV_MSG_FREQ = 10 # how often do we want to get messages from mavlink (in Hz)


if __name__ == "__main__":
   logger.info("Starting hackathon 2026")

   try:
      mavLink:MavLinkHandler = MavLinkHandler(MAV_COM,MAV_MSG_FREQ) 

   except Exception as e:
      logger.error("Unable to connect to FC")
      logger.error(f"Error: {e}")
      quit()
      
   # # wait 4 GUIDED mode
   # mavLink.check_until_guided()

   #getting the drone current live location


   while True:
      if new_rssi():
         rssi = get_rssi()
         curr_time = time.asctime()
         lat ,lon, alt = mavLink.get_gps_coordinates(MAV_COM, timeout=10)
         print(f"Latitude:  {lat}°")
         print(f"Longitude: {lon}°")
         print(f"Altitude:  {alt} m")
         lines_list = [
         f"lat ={lat}\n",
         f"lon ={lon}\n",
         ]

         with open("data.txt", "w", encoding="utf-8") as file:
            file.writelines(lines_list)

      # wait for mission to end
   
   quit()