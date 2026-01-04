
import json
import requests
from datetime import datetime

# Configuration
ES_HOST = "http://localhost:9200"
LOG_FILE = "uploads/fresh_logs_2026_01_04.json"
INDEX_PREFIX = "saas-logs-"

def load_logs():
    print(f"Reading logs from {LOG_FILE}...")
    with open(LOG_FILE, 'r') as f:
        logs = [json.loads(line) for line in f]
    
    print(f"Found {len(logs)} logs.")
    
    bulk_data = []
    for i, log in enumerate(logs):
        # Determine index based on timestamp
        ts = log.get('timestamp')
        if ts:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            index_name = f"{INDEX_PREFIX}{dt.strftime('%Y.%m.%d')}"
            log['@timestamp'] = ts # Add @timestamp for Kibana/App compatibility
        else:
            index_name = f"{INDEX_PREFIX}{datetime.now().strftime('%Y.%m.%d')}"
            log['@timestamp'] = datetime.now().isoformat()
            
            
        # Action line
        action = {
            "index": {
                "_index": index_name
            }
        }
        bulk_data.append(json.dumps(action))
        
        # Data line (convert types if needed, ES dynamic mapping handles most)
        bulk_data.append(json.dumps(log))
        
        # Send in batches of 1000
        if len(bulk_data) >= 2000:
            send_bulk(bulk_data)
            bulk_data = []
            
    # Send remaining
    if bulk_data:
        send_bulk(bulk_data)

def send_bulk(bulk_data):
    if not bulk_data:
        return
        
    # JSON content requires newline at end of each line
    body = "\n".join(bulk_data) + "\n"
    
    url = f"{ES_HOST}/_bulk"
    headers = {"Content-Type": "application/x-ndjson"}
    
    try:
        response = requests.post(url, headers=headers, data=body)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get('errors'):
                print(f"⚠️  Bulk insert had errors: {res_json['errors']}")
            else:
                print(f"✅ Batch sent successfully.")
        else:
            print(f"❌ Failed to send batch: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception sending batch: {e}")

if __name__ == "__main__":
    load_logs()
