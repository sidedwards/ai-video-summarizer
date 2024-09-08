import os
import logging
import json
import requests
import time
import subprocess
from utils import prompt_for_file, load_config

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def upload_to_s3(file_path, config):
    command = f"{config['aws_cli_path']} s3 cp {file_path} s3://{config['s3_bucket']}/public/{os.path.basename(file_path)}"
    subprocess.run(command, shell=True, check=True)

def get_s3_presigned_url(file_name, config):
    command = f"{config['aws_cli_path']} s3 presign s3://{config['s3_bucket']}/public/{file_name}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def start_transcription(url, config):
    headers = {
        "Authorization": f"Bearer {config['replicate_api_key']}",
        "Content-Type": "application/json"
    }
    data = {
        "version": config['replicate_model_version'],
        "input": {
            "debug": False,
            "language": "en",
            "vad_onset": 0.5,
            "audio_file": url,
            "batch_size": 64,
            "vad_offset": 0.363,
            "diarization": False,
            "temperature": 0,
            "align_output": False,
            "huggingface_access_token": config['huggingface_token'],
            "language_detection_min_prob": 0,
            "language_detection_max_tries": 5
        }
    }
    response = requests.post(config['replicate_api_url'], headers=headers, json=data)
    return response.json()

def get_transcription_result(prediction_url, config):
    headers = {"Authorization": f"Bearer {config['replicate_api_key']}"}
    while True:
        response = requests.get(prediction_url, headers=headers)
        result = response.json()
        if result['status'] == "succeeded":
            return result['output']['segments']
        elif result['status'] == "failed":
            raise Exception("Transcription process failed.")
        time.sleep(5)

def generate_meeting_minutes(transcript, config):
    headers = {
        "x-api-key": config['anthropic_api_key'],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": config['anthropic_model'],
        "temperature": 0,
        "max_tokens": 4000,
        "messages": [
            {"role": "user", "content": f"Create very detailed meeting minutes based on the following transcription: {json.dumps(transcript)}"}
        ]
    }
    response = requests.post(config['anthropic_api_url'], headers=headers, json=data)
    return response.json()['content'][0]['text']

def create_video_clips(transcript, meeting_minutes, source_file, dest_folder, config):
    # First, let's extract key topics from the meeting minutes
    topic_extraction_message = f"""
    Based on the following meeting minutes, extract the main discussion topics:
    {meeting_minutes}

    For each topic, provide:
    1. A short, descriptive title (max 5 words)
    2. A list of related keywords (max 5 keywords)

    Format the response as a JSON array of objects, each containing 'title' and 'keywords' fields.
    """

    headers = {
        "x-api-key": config['anthropic_api_key'],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    topic_extraction_data = {
        "model": "claude-3-opus-20240229",
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": topic_extraction_message}
        ]
    }
    
    topic_response = requests.post(config['anthropic_api_url'], headers=headers, json=topic_extraction_data)
    topics = json.loads(topic_response.json()['content'][0]['text'])

    # Now, let's find relevant segments for each topic
    clip_generation_message = f"""
    For each of the following topics, find the most relevant segment in the transcript:
    {json.dumps(topics)}

    Transcript:
    {json.dumps(transcript)}

    For each topic:
    1. Find the segment that best represents the topic.
    2. If the segment is longer than 2 minutes, trim it to the most relevant 2-minute portion.
    3. Ensure that the segment starts and ends at natural breaks in the conversation.

    Provide the results as a JSON array of objects, each containing:
    - title: The topic title
    - start: Start time of the clip (in seconds)
    - end: End time of the clip (in seconds)

    The clips should not overlap.
    """

    clip_generation_data = {
        "model": "claude-3-opus-20240229",
        "max_tokens": 2000,
        "messages": [
            {"role": "user", "content": clip_generation_message}
        ]
    }

    clip_response = requests.post(config['anthropic_api_url'], headers=headers, json=clip_generation_data)
    clips = json.loads(clip_response.json()['content'][0]['text'])

    # Generate FFmpeg commands
    ffmpeg_commands = []
    for clip in clips:
        safe_title = ''.join(c for c in clip['title'] if c.isalnum() or c in (' ', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        output_file = os.path.join(dest_folder, f"{safe_title}.mp4")
        command = f"/opt/homebrew/bin/ffmpeg -i {source_file} -ss {clip['start']} -to {clip['end']} -y -c copy {output_file}"
        ffmpeg_commands.append(command)

    return ' && '.join(ffmpeg_commands)

def execute_ffmpeg_commands(commands):
    for command in commands.split('&&'):
        subprocess.run(command.strip(), shell=True, check=True)

def main():
    try:
        logging.info("Starting main function")
        
        config = load_config()
        logging.info("Configuration loaded successfully")
        
        video_file = prompt_for_file('.mp4')
        if video_file is None:
            logging.error("No video file selected. Exiting.")
            return
        logging.info(f"Selected video file: {video_file}")
        
        upload_to_s3(video_file, config)
        logging.info("Video file uploaded to S3")
        
        presigned_url = get_s3_presigned_url(os.path.basename(video_file), config)
        logging.info("Got presigned URL for the video file")
        
        prediction = start_transcription(presigned_url, config)
        logging.info("Transcription process started")
        
        transcript = get_transcription_result(prediction['urls']['get'], config)
        logging.info("Transcription completed")
        
        meeting_minutes = generate_meeting_minutes(transcript, config)
        logging.info("Meeting minutes generated")
        
        meeting_name = os.path.splitext(os.path.basename(video_file))[0]
        meeting_folder = os.path.join(os.path.dirname(video_file), meeting_name)
        os.makedirs(meeting_folder, exist_ok=True)
        
        with open(os.path.join(meeting_folder, f"{meeting_name}.md"), 'w') as f:
            f.write(meeting_minutes)
        logging.info(f"Created {meeting_name}.md")

        ffmpeg_commands = create_video_clips(transcript, meeting_minutes, video_file, meeting_folder, config)
        logging.info("FFmpeg commands generated")

        execute_ffmpeg_commands(ffmpeg_commands)
        logging.info("Video clips created")

        logging.info("Main function completed successfully")
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()

