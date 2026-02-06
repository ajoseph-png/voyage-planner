import requests
import csv
import time
from datetime import datetime

# Global store for the current hour's data
current_hour_cache = None
last_fetch_hour = None


def fetch_windy_data(lat, lon, model, parameters, api_key):
    url = "https://api.windy.com/api/point-forecast/v2"
    headers = {"Content-Type": "application/json"}
    data = {
        "lat": float(lat),
        "lon": float(lon),
        "model": model,
        "parameters": parameters,
        "levels": ["surface"],
        "key": api_key
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  [Error] {model} fetch failed: {e}")
        return None


def process_csv_and_fetch(input_filename, output_filename, api_key):
    global current_hour_cache, last_fetch_hour
    all_results = []
    unique_params = set()

    with open(input_filename, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            target_time_str = row['Timestamp_UTC']
            lat = row['Latitude']
            lon = row['Longitude']

            try:
                # Parse timestamp and identify the specific hour
                dt = datetime.fromisoformat(target_time_str.replace('Z', '+00:00'))
                current_row_hour = dt.strftime('%Y-%m-%d %H')  # e.g., "2026-02-06 06"
                target_ts_ms = dt.timestamp() * 1000
            except ValueError:
                print(f"Skipping row: Invalid timestamp format '{target_time_str}'")
                continue

            # LOGIC: If this row's hour is different from the last fetch, call the API
            if current_row_hour != last_fetch_hour:
                print(f"\n--- New Hour Detected ({current_row_hour}:00). Fetching from API... ---")

                # Reset cache for the new hour
                new_weather_data = {}
                tasks = [
                    {"model": "gfs", "params": ["wind", "temp"]},
                    {"model": "gfsWave", "params": ["waves"]}
                ]

                for task in tasks:
                    data = fetch_windy_data(lat, lon, task['model'], task['params'], api_key)

                    if data and 'ts' in data:
                        timestamps = data['ts']
                        # Find closest index to the first minute of this new hour
                        idx = min(range(len(timestamps)), key=lambda i: abs(timestamps[i] - target_ts_ms))

                        params_found = [p for p in data.keys() if p not in ['ts', 'units', 'header']]
                        for p in params_found:
                            val = data[p][idx] if idx < len(data[p]) else "N/A"
                            new_weather_data[p] = val
                            unique_params.add(p)

                # Update globals
                current_hour_cache = new_weather_data
                last_fetch_hour = current_row_hour

                # API safety delay
                time.sleep(1)
            else:
                print(f"  > Using cached hour data for minute: {dt.minute}")

            # Combine the cached weather with current row metadata
            combined_entry = {
                "Input_Timestamp": target_time_str,
                "Latitude": lat,
                "Longitude": lon,
                **current_hour_cache  # Merges all weather parameters into this dict
            }

            print(f"  Recording Row: {combined_entry}")
            all_results.append(combined_entry)

    # Save to CSV
    if not all_results:
        print("No data retrieved.")
        return

    headers = ["Input_Timestamp", "Latitude", "Longitude"] + sorted(list(unique_params))
    with open(output_filename, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\n✅ Done! Hourly-synced data saved to {output_filename}")


if __name__ == "__main__":
    API_KEY = "OWOrZP856kwh13SlDfHFTbCnciNt19dk"
    process_csv_and_fetch("voyage_plan.csv", "weather_results.csv", API_KEY)