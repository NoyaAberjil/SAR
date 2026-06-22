import numpy as np
from scipy.optimize import least_squares

# ==========================================
# פונקציות עזר להמרת קואורדינטות (GPS <-> מטרים)
# ==========================================
def rssi_to_distance(rssi, rssi_0=-30.0, n=2.0, d_0=1.0):
    """
    Estimates distance from RSSI using the Log-Distance Path Loss Model.
    
    Parameters:
    ----------
    rssi : float or ndarray
        The measured signal strength (dBm) from the RTL-SDR.
    rssi_0 : float, optional
        The calibrated signal strength (dBm) at a known reference distance (d_0).
        Default is -30.0 dBm (typical for a phone ~1 meter away).
    n : float, optional
        The path loss exponent. 
        Default is 2.0 (ideal for open space / desert environments).
    d_0 : float, optional
        The reference distance (meters). Default is 1.0 meter.
        
    Returns:
    -------
    float or ndarray
        The estimated distance to the target in meters.
    """
    # Math: d = d_0 * 10^((rssi_0 - rssi) / (10 * n))
    exponent = (rssi_0 - rssi) / (10.0 * n)
    return d_0 * (10.0 ** exponent)


def gps_to_local_meters(lat, lon, ref_lat, ref_lon):
    """ממירה קואורדינטות GPS למרחק במטרים (X, Y) מנקודת ייחוס"""
    # מעלת קו רוחב אחת שווה תמיד לכ-111,132.95 מטרים
    meters_per_degree = 111132.95
    
    # המרת קו הרוחב לרדיאנים עבור חישוב קו האורך
    ref_lat_rad = np.radians(ref_lat)
    
    # חישוב המרחקים
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

# ==========================================
# אלגוריתם האופטימיזציה (Trilateration)
# ==========================================

def trilateration_residuals(target_pos_meters, drone_positions_meters, estimated_distances):
    """מחשבת את השארית (השגיאה) במטרים עבור הניחוש הנוכחי"""
    tx, ty = target_pos_meters
    
    # מרחק גיאומטרי מנקודת הניחוש לכל מיקומי הרחפן
    calculated_distances = np.sqrt((drone_positions_meters[:, 0] - tx)**2 + (drone_positions_meters[:, 1] - ty)**2)
    
    # השגיאה: ההפרש בין המרחק המחושב למרחק שנקלט מהרדיו
    return calculated_distances - estimated_distances

# ==========================================
# הרצה בדיקה עם נתוני אמת (סימולציה)
# ==========================================

# 1. נתונים שנאספו מהרחפן (Lat, Lon)
drone_gps_data = np.array([
    [30.9871, 34.9121], # נקודה 1
    [30.9895, 34.9152], # נקודה 2
    [30.9912, 34.9110], # נקודה 3
    [30.9860, 34.9165]  # נקודה 4
])

# המרחקים המוערכים מהטלפון (במטרים) כפי שחושבו מה-RSSI בכל נקודה
measured_distances = np.array([320.0, 210.0, 450.0, 290.0])

# 2. קביעת נקודת הייחוס (ניקח את הנקודה הראשונה של הרחפן כ-0,0)
ref_lat = drone_gps_data[0, 0]
ref_lon = drone_gps_data[0, 1]

# 3. המרת כל מיקומי הרחפן למטרים מקומיים
drone_meters = []
for lat, lon in drone_gps_data:
    x, y = gps_to_local_meters(lat, lon, ref_lat, ref_lon)
    drone_meters.append([x, y])
drone_meters = np.array(drone_meters)

# 4. ניחוש ראשוני במטרים (המיקום הממוצע של הרחפן הוא נקודת התחלה טובה)
initial_guess_meters = np.mean(drone_meters, axis=0)

# 5. הרצת אופטימיזציית Least Squares במטרים
result = least_squares(
    trilateration_residuals, 
    initial_guess_meters, 
    args=(drone_meters, measured_distances)
)

# 6. חילוץ נקודת המינימום (X, Y במטרים) והמרתה חזרה ל-GPS
best_x, best_y = result.x
target_lat, target_lon = local_meters_to_gps(best_x, best_y, ref_lat, ref_lon)

# ==========================================
# הדפסת התוצאות
# ==========================================
print("--- TRILATERATION RESULTS ---")
print(f"Calculated Local Offset: X = {best_x:.2f}m, Y = {best_y:.2f}m from takeoff")
print(f"Predicted Target GPS   : Lat = {target_lat:.6f}, Lon = {target_lon:.6f}")
print(f"Google Maps Link       : https://www.google.com/maps/search/?api=1&query={target_lat},{target_lon}")