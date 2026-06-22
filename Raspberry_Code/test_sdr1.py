import time
import numpy as np
from rtlsdr import RtlSdr

print("Initializing RTL-SDR...")
try:
    sdr = RtlSdr()
    sdr.sample_rate = 2.4e6
    sdr.center_freq = 434.0e6  # תדר לבדיקה
    sdr.gain = 40.0

    print("SDR Ready! Reading signal power (Press Ctrl+C to stop):")
    print("-" * 40)

    while True:
        samples = sdr.read_samples(1024 * 16)
        power = np.mean(np.abs(samples) ** 2)
        power_db = 10 * np.log10(power)
        
        print(f"Freq: {sdr.center_freq/1e6} MHz | Signal Power: {power_db:.2f} dB", end='\r')
        time.sleep(0.1)

except Exception as e:
    print(f"Error occurred: {e}")
finally:
    try:
        sdr.close()
        print("\nSDR closed safely.")
    except:
        pass