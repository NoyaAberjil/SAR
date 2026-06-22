import time
import numpy as np
from rtlsdr import RtlSdr
from scipy.optimize import least_squares

# ==========================================
# 1. הגדרות ופרמטרים קבועים
# ==========================================
# רשימת תדרי האמצע לסריקה (Uplink בישראל - דור 4)
# דילוגים של 2MHz כדי להבטיח כיסוי יעיל ברוחב הפס של ה-SDR
UP_BAND_28 = list(np.arange(704.0e6, 748.0e6, 2.0e6)) # 700 MHz
UP_BAND_20 = list(np.arange(834.0e6, 862.0e6, 2.0e6)) # 800 MHz
UP_BAND_8  = list(np.arange(882.0e6, 915.0e6, 2.0e6)) # 900 MHz

SCAN_FREQUENCIES = UP_BAND_28 + UP_BAND_20 + UP_BAND_8

# פרמטרים למודל המרת RSSI למרחק
RSSI_0 = -35.0  # עוצמת אות מכוילת במרחק של מטר אחד (ב-dBm)
N_EXPONENT = 2.2 # מקדם ניחות הסביבה במדבר פתוח
D_0 = 1.0        # מרחק הייחוס (מטר אחד)

# ==========================================
# 2. פונקציות עזר גיאוגרפיות ורדיו
# ==========================================
def gps_to_local_meters(lat, lon, ref_lat, ref_lon):
    """ממירה קואורדינטות GPS למרחק במטרים (X, Y) מנקודת ייחוס"""
    meters_per_degree = 111132.95
    ref_lat_rad = np.radians(ref_lat)
    y = (lat - ref_lat) * meters_per_degree
    x = (lon - ref_lon) * meters_per_degree * np.cos(ref_lat_rad)
    return x, y

def local_meters_to_gps(x, y, ref_lat, ref_lon):
    """ממירה מרחק במטרים (X, Y) בחזרה לקואורדינטות GPS"""
    meters_per_degree = 111132.95
    ref_lat_rad = np.radians(ref_lat)
    lat = ref_lat + (y / meters_per_degree)
    lon = ref_lon + (x / (meters_per_degree * np.cos(ref_lat_rad)))
    return lat, lon

def rssi_to_distance(rssi, rssi_0=RSSI_0, n=N_EXPONENT, d_0=D_0):
    """מחשבת מרחק מוערך במטרים על בסיס עוצמת אות RSSI"""
    exponent = (rssi_0 - rssi) / (10.0 * n)
    return d_0 * (10.0 ** exponent)

# ==========================================
# 3. אלגוריתם האופטימיזציה והחיתוך
# ==========================================
def trilateration_residuals(target_pos_meters, drone_positions_meters, estimated_distances):
    """פונקציית השאריות עבור אלגוריתם ה-Least Squares"""
    tx, ty = target_pos_meters
    calculated_distances = np.sqrt((drone_positions_meters[:, 0] - tx)**2 + (drone_positions_meters[:, 1] - ty)**2)
    return calculated_distances - estimated_distances

def calculate_target_gps(data_points):
    """
    מקבלת רשימה של דגימות: [(lat, lon, distance), ...]
    ומחזירה את ה-GPS המשוער של המטרה
    """
    if len(data_points) < 3:
        print("Not enough data points for trilateration (Need at least 3).")
        return None
        
    points = np.array(data_points)
    drone_gps = points[:, 0:2]
    distances = points[:, 2]
    
    # נקודת ייחוס (נקודת הדגימה הראשונה)
    ref_lat, ref_lon = drone_gps[0, 0], drone_gps[0, 1]
    
    # המרה למטרים
    drone_meters = []
    for lat, lon in drone_gps:
        x, y = gps_to_local_meters(lat, lon, ref_lat, ref_lon)
        drone_meters.append([x, y])
    drone_meters = np.array(drone_meters)
    
    # ניחוש ראשוני במרכז הדגימות
    initial_guess = np.mean(drone_meters, axis=0)
    
    # הרצת האופטימיזציה
    result = least_squares(trilateration_residuals, initial_guess, args=(drone_meters, distances))
    
    # המרה חזרה ל-GPS
    best_x, best_y = result.x
    target_lat, target_lon = local_meters_to_gps(best_x, best_y, ref_lat, ref_lon)
    return target_lat, target_lon

# ==========================================
# 4. פונקציית דמה לקבלת GPS מהרחפן (סימולציה)
# ==========================================
def get_mock_drone_gps(step):
    """סימולציה של מסלול טיסה של רחפן בנגב"""
    flight_path = [
        [30.9871, 34.9121],
        [30.9895, 34.9152],
        [30.9912, 34.9110],
        [30.9860, 34.9165],
        [30.9850, 34.9115]
    ]
    return flight_path[step % len(flight_path)]

# ==========================================
# 5. הלולאה המרכזית (Main Execution)
# ==========================================
def main():
    print("--- [SignalScout] System Initializing ---")
    
    try:
        sdr = RtlSdr()
        sdr.sample_rate = 2.4e6
        sdr.gain = 45.0  # הגבר גבוה לקליטת אותות חלשים בשטח
    except Exception as e:
        print(f"Failed to initialize RTL-SDR: {e}")
        return

    collected_data = []
    max_test_steps = 5  # נבצע 5 מדידות בשטח כפי שביקשת
    
    print("\nPhase 1: Scanning Uplink Bands for Cell Phone Activity...")
    print("-" * 60)
    
    try:
        for step in range(max_test_steps):
            # 1. קבלת המיקום הנוכחי של הרחפן
            drone_lat, drone_lon = get_mock_drone_gps(step)
            
            best_rssi = -100.0
            best_freq = 0.0
            
            # 2. סריקה מהירה (Frequency Hopping) כדי למצוא את האות הכי חזק בנקודה זו
            for freq in SCAN_FREQUENCIES:
                sdr.center_freq = freq
                time.sleep(0.01) # זמן קצר להתייצבות התדר במקלט
                
                # קריאת דגימות וחישוב עוצמה (RSSI)
                samples = sdr.read_samples(1024 * 8)
                power = np.mean(np.abs(samples) ** 2)
                rssi = 10 * np.log10(power)
                print(f"Step {step+1}: Scanned {freq/1e6:.2f} MHz | RSSI: {rssi:.2f} dBm")
                if rssi > best_rssi:
                    best_rssi = rssi
                    best_freq = freq
            
            # 3. המרת ה-RSSI של התדר המוביל למרחק במטרים
            estimated_dist = rssi_to_distance(best_rssi)
            
            # 4. שמירת הנתונים בזיכרון
            collected_data.append([drone_lat, drone_lon, estimated_dist])
            
            print(f"Measurement {step+1}/{max_test_steps}:")
            print(f"  Drone Position : Lat={drone_lat:.5f}, Lon={drone_lon:.5f}")
            print(f"  Detected Signal: {best_freq/1e6:.2f} MHz | RSSI: {best_rssi:.2f} dBm")
            print(f"  Est. Distance  : {estimated_dist:.2f} meters")
            print("-" * 60)
            
            time.sleep(1.0) # המתנה בין נקודות דגימה של הרחפן
            
        # סגירת ה-SDR בסיום איסוף הנתונים
        sdr.close()
        
        # 5. הרצת שלב האופטימיזציה (Least Squares) לחילוץ המיקום הסופי
        print("\nPhase 2: Running Non-Linear Least Squares Trilateration...")
        target_gps = calculate_target_gps(collected_data)
        
        if target_gps:
            target_lat, target_lon = target_gps
            print("\n=================== TARGET LOCATED ===================")
            print(f"Estimated Target GPS: Lat = {target_lat:.6f}, Lon = {target_lon:.6f}")
            print(f"Google Maps Link    : https://maps.google.com/?q={target_lat},{target_lon}")
            print("======================================================")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    finally:
        try:
            sdr.close()
        except:
            pass

if __name__ == "__main__":
    main()