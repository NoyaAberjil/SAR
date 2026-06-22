
import time
import numpy as np
import matplotlib.pyplot as plt
from rtlsdr import RtlSdr

# 1. Hardware Initialization
sdr = RtlSdr()
# sdr.sample_rate = 1.2e6
sdr.sample_rate = 2.4e6
sdr.center_freq = 434.418e6
sdr.gain = 40.0

# 32k sample blocks give an excellent balance of speed and frequency resolution
SAMPLE_BLOCK_SIZE = 1024 * 32  

# Smoothing configuration for the terminal printout
MOVING_AVG_WINDOW = 10
power_history = []

# Variables to capture the peak event for post-processing
max_observed_power_db = -999.0
peak_samples = None

print(f"Recording started on {sdr.center_freq/1e6} MHz...")
print("The script will capture and save the spectrum of your STRONGEST signal.")
print("Press Ctrl+C to stop recording and generate the plot.")
print("-" * 60)

try:
    while True:
        # A. Fetch data and eliminate hardware DC spike
        samples = sdr.read_samples(SAMPLE_BLOCK_SIZE)
        samples = samples - np.mean(samples)
        
        # B. Calculate and smooth the total numeric power
        instant_power = np.mean(np.abs(samples) ** 2)
        power_history.append(instant_power)
        if len(power_history) > MOVING_AVG_WINDOW:
            power_history.pop(0)
        
        smoothed_power = np.mean(power_history)
        power_db = 10 * np.log10(smoothed_power) if smoothed_power > 0 else -40
        
        # C. Check if this is the strongest signal we've seen so far
        if power_db > max_observed_power_db:
            max_observed_power_db = power_db
            peak_samples = samples  # Keep a snapshot of these raw IQ samples in memory
            
        # D. Print current status to terminal
        print(f"Current: {power_db:.2f} dB | Peak Recorded: {max_observed_power_db:.2f} dB", end='\r')
        
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n\nRecording stopped by user. Processing peak data...")

finally:
    # Always turn off the hardware first
    sdr.close()
    print("SDR hardware safely closed.")

# --- POST-PROCESSING SECTION (Runs after you press Ctrl+C) ---

if peak_samples is not None:
    print(f"Generating FFT plot for the peak signal event ({max_observed_power_db:.2f} dB)...")
    
    # 1. Compute the FFT of the peak snapshot
    fft_data = np.fft.fft(peak_samples)
    fft_shifted = np.fft.fftshift(fft_data)
    fft_power_db = 10 * np.log10(np.abs(fft_shifted) ** 2 / SAMPLE_BLOCK_SIZE)
    
    # 2. Generate frequency axis mapping
    freq_axis = np.fft.fftshift(np.fft.fftfreq(SAMPLE_BLOCK_SIZE, 1/sdr.sample_rate))
    freq_axis_mhz = (freq_axis + sdr.center_freq) / 1e6
    
    # 3. Create the static chart
    plt.figure(figsize=(10, 6))
    plt.plot(freq_axis_mhz, fft_power_db, color='darkblue', linewidth=0.8)
    
    # Chart styling
    plt.title(f"Captured Peak Spectrum Analyzer Snapshot\nMax Power Logged: {max_observed_power_db:.2f} dB", fontsize=12, fontweight='bold')
    plt.xlabel("Frequency [MHz]", fontsize=10)
    plt.ylabel("Relative Power [dB]", fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.ylim(-40, 20)
    plt.axvline(sdr.center_freq/1e6, color='red', linestyle=':', alpha=0.7, label='Center Frequency')
    plt.legend()
    
    # Save chart to the local directory
    output_image = "capture_fft.png"
    plt.savefig(output_image, dpi=150)
    print(f"Success! Final spectrum plot saved to disk as: {output_image}")
else:
    print("No valid signal data was captured.")