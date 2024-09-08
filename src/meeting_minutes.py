import requests
import json

def generate_meeting_minutes(transcript, config):
    prompt = f"Create very detailed meeting minutes based on the following transcript:\n\n{transcript}"
    
    headers = {
        "x-api-key": config['anthropic_api_key'],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": config['anthropic_model'],
        "max_tokens": 4000,
        "temperature": 0,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    response = requests.post(config['anthropic_api_url'], headers=headers, json=data)
    response_json = response.json()
    
    if 'content' in response_json and len(response_json['content']) > 0:
        meeting_minutes = response_json['content'][0]['text']
    else:
        raise Exception("Failed to generate meeting minutes")

    return meeting_minutes

