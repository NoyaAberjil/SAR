
import time
import numpy as np
from rtlsdr import RtlSdr
from logger import logger
from mavlink import *
from collections import deque # FIX 1: Import deque instead of queue
import time
from requests import post 

MAV_COM="/dev/ttyACM0"
MAV_MSG_FREQ = 10 # how often do we want to get messages from mavlink (in Hz)
URL = "http://192.168.1.4:8080/api/add_pin"  # Replace with your server URL

MIN_DB = -10

logger.info("Starting hackathon 2026")
try:
      mavLink:MavLinkHandler = MavLinkHandler(MAV_COM,MAV_MSG_FREQ) 

except Exception as e:
      logger.error("Unable to connect to FC")
      logger.error(f"Error: {e}")
      quit()
      
print("Initializing RTL-SDR...")
try:
    sdr = RtlSdr()
    sdr.sample_rate = 2.4e6
    sdr.center_freq = 434.418e6
    sdr.gain = 40.0

    print("SDR Ready! Reading signal power (Press Ctrl+C to stop):")
    print("-" * 40)

    while True:
        samples = sdr.read_samples(1024 * 16)
        power = np.mean(np.abs(samples) ** 2)
        power_db = 10 * np.log10(power)
        
    
        print(f"Freq: {sdr.center_freq/1e6} MHz | Signal Power: {power_db:.2f} dB", end='\r')
        if power_db > MIN_DB:
            print(f"Freq: {sdr.center_freq/1e6} MHz | Signal Power: {power_db:.2f} dB")
            print("Below threshold")
            lat ,lon, alt = mavLink.get_gps_coordinates(MAV_COM, timeout=10)
            print(f"GPS Coordinates: Latitude={lat}, Longitude={lon}, Altitude={alt} meters")
            rsl = post(URL, json={"lat": lat, "lon": lon, "type":"Other"})
            print(f"Posted to server: {rsl.status_code} | Response: {rsl.text}")
            time.sleep(2)
        time.sleep(0.1)

except Exception as e:
    print(f"Error occurred: {e}")
finally:
    try:
        sdr.close()
        print("\nSDR closed safely.")
    except:
        pass

