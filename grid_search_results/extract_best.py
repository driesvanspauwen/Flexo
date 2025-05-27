import json

def extract_best_config(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)

    best_entry = max(data, key=lambda entry: entry['score'])

    config = best_entry['config']
    score = best_entry['score']
    timestamp = best_entry['timestamp']

    print("Best configuration:")
    print(f"  RET_WM_DIV_ROUNDS: {config['RET_WM_DIV_ROUNDS']}")
    print(f"  WM_DELAY: {config['WM_DELAY']}")
    print(f"  WR_OFFSET: {config['WR_OFFSET']}")
    print(f"  Score: {score}")
    print(f"  Timestamp: {timestamp}")

if __name__ == "__main__":
    extract_best_config("results_20250524_223410.json")