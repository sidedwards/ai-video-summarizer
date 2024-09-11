import os
import logging
import json
import re
import requests
import time
import subprocess
from utils import prompt_for_goal, prompt_for_media_file, load_config
from transcription_goal import TranscriptionGoal

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def upload_to_s3(file_path, config):
    logger.debug(f"Uploading file to S3: {file_path}")
    command = f"{config['aws_cli_path']} s3 cp {file_path} s3://{config['s3_bucket']}/public/{os.path.basename(file_path)}"
    logger.debug(f"S3 upload command: {command}")
    subprocess.run(command, shell=True, check=True)
    logger.info(f"File uploaded successfully to S3: {file_path}")

def get_s3_presigned_url(file_name, config):
    logger.debug(f"Getting presigned URL for file: {file_name}")
    command = f"{config['aws_cli_path']} s3 presign s3://{config['s3_bucket']}/public/{file_name}"
    logger.debug(f"S3 presign command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
    presigned_url = result.stdout.strip()
    logger.info(f"Presigned URL generated: {presigned_url}")
    return presigned_url

def start_transcription(url, config):
    logger.debug(f"Starting transcription for URL: {url}")
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
    logger.debug(f"Sending request to Replicate API: {config['replicate_api_url']}")
    response = requests.post(config['replicate_api_url'], headers=headers, json=data)
    logger.debug(f"Replicate API response: {response.text}")
    return response.json()

def get_transcription_result(prediction_url, config):
    logger.debug(f"Getting transcription result from: {prediction_url}")
    headers = {"Authorization": f"Bearer {config['replicate_api_key']}"}
    while True:
        response = requests.get(prediction_url, headers=headers)
        result = response.json()
        logger.debug(f"Transcription status: {result['status']}")
        if result['status'] == "succeeded":
            logger.info("Transcription completed successfully")
            return result['output']['segments']
        elif result['status'] == "failed":
            logger.error("Transcription process failed")
            raise Exception("Transcription process failed.")
        time.sleep(5)

def generate_content(transcript, goal, config):
    logger.debug(f"Generating content for goal: {goal.value}")
    headers = {
        "x-api-key": config['anthropic_api_key'],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    prompts = {
        TranscriptionGoal.MEETING_MINUTES: "Create very detailed meeting minutes based on the following transcription:",
        TranscriptionGoal.PODCAST_SUMMARY: "Summarize this podcast episode, highlighting key points and interesting discussions:",
        TranscriptionGoal.LECTURE_NOTES: "Create comprehensive lecture notes from this transcription, organizing key concepts and examples:",
        TranscriptionGoal.INTERVIEW_HIGHLIGHTS: "Extract the main insights and notable quotes from this interview transcription:",
        TranscriptionGoal.GENERAL_TRANSCRIPTION: "Provide a clear and concise summary of the main points discussed in this transcription:"
    }

    prompt = prompts.get(goal, prompts[TranscriptionGoal.GENERAL_TRANSCRIPTION])

    data = {
        "model": config['anthropic_model'],
        "temperature": 0,
        "max_tokens": 4000,
        "messages": [
            {"role": "user", "content": f"{prompt} {json.dumps(transcript)}"}
        ]
    }
    logger.debug(f"Sending request to Anthropic API: {config['anthropic_api_url']}")
    response = requests.post(config['anthropic_api_url'], headers=headers, json=data)
    logger.debug(f"Anthropic API response: {response.text}")
    return response.json()['content'][0]['text']

def create_media_clips(transcript, content, source_file, dest_folder, goal, config):
    logger.debug(f"Creating media clips for goal: {goal.value}")
    # ... (rest of the function remains the same)
    logger.debug(f"Generated FFmpeg commands: {ffmpeg_commands}")
    return ' && '.join(ffmpeg_commands)

def execute_ffmpeg_commands(commands):
    logger.debug(f"Executing FFmpeg commands: {commands}")
    for command in commands.split('&&'):
        logger.debug(f"Executing command: {command.strip()}")
        subprocess.run(command.strip(), shell=True, check=True)
    logger.info("All FFmpeg commands executed successfully")

def main(media_file, goal=TranscriptionGoal.GENERAL_TRANSCRIPTION, progress_callback=None):
    try:
        logger.info(f"Starting main process for file: {media_file}")
        if progress_callback:
            progress_callback("Starting transcription process", 0)
        
        config = load_config()
        logger.debug(f"Loaded configuration: {config}")
        
        if progress_callback:
            progress_callback("Uploading media to S3", 10)
        upload_to_s3(media_file, config)
        
        if progress_callback:
            progress_callback("Getting presigned URL", 20)
        presigned_url = get_s3_presigned_url(os.path.basename(media_file), config)
        
        if progress_callback:
            progress_callback("Starting transcription", 30)
        prediction = start_transcription(presigned_url, config)
        
        if progress_callback:
            progress_callback("Processing transcription", 40)
        transcript = get_transcription_result(prediction['urls']['get'], config)
        
        if progress_callback:
            progress_callback(f"Generating {goal.value.replace('_', ' ')}", 60)
        content = generate_content(transcript, goal, config)
        
        output_name = os.path.splitext(os.path.basename(media_file))[0]
        output_folder = os.path.join(os.path.dirname(media_file), output_name)
        os.makedirs(output_folder, exist_ok=True)
        
        output_file = os.path.join(output_folder, f"{output_name}_{goal.value}.md")
        logger.info(f"Writing content to file: {output_file}")
        with open(output_file, 'w') as f:
            f.write(content)
        
        if progress_callback:
            progress_callback("Creating media clips", 80)
        ffmpeg_commands = create_media_clips(transcript, content, media_file, output_folder, goal, config)
        
        execute_ffmpeg_commands(ffmpeg_commands)
        
        if progress_callback:
            progress_callback("Process complete", 100)
        
        logger.info("Main process completed successfully")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Script started")
    media_file = prompt_for_media_file()
    if media_file:
        logger.info(f"Media file selected: {media_file}")
        goal = prompt_for_goal()
        logger.info(f"Transcription goal selected: {goal.value}")
        main(media_file, goal)
    else:
        logger.warning("No media file selected. Exiting.")