import os
import logging
from logging.handlers import RotatingFileHandler
import json
import re
import requests
import time
import subprocess
import asyncio
import zipfile
import tempfile
from fastapi import FastAPI, File, UploadFile, Form, Depends, BackgroundTasks
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from enum import Enum
from utils import load_config
from transcription_goal import TranscriptionGoal

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        RotatingFileHandler('debug.log', maxBytes=10000000, backupCount=5),
                        logging.StreamHandler()
                    ])
logging.getLogger('multipart').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Global variables
processing_status = None
zip_file_path = None
config = load_config()

# FastAPI app setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranscriptionGoal(str, Enum):
    GENERAL_TRANSCRIPTION = "GENERAL_TRANSCRIPTION"
    MEETING_MINUTES = "MEETING_MINUTES"
    PODCAST_SUMMARY = "PODCAST_SUMMARY"
    LECTURE_NOTES = "LECTURE_NOTES"
    INTERVIEW_HIGHLIGHTS = "INTERVIEW_HIGHLIGHTS"

class ProcessingStatus(BaseModel):
    status: str
    progress: int
    message: str

def update_processing_status(status: str, progress: int, message: str):
    global processing_status
    processing_status = ProcessingStatus(status=status, progress=progress, message=message)
    logger.info(f"Status Update: {status} - Progress: {progress}% - Message: {message}")
    return processing_status

def save_debug_info(output_folder, content, topics, clips):
    debug_file = os.path.join(output_folder, "debug_info.txt")
    with open(debug_file, "w") as f:
        f.write("Generated Content:\n")
        f.write(content)
        f.write("\n\nExtracted Topics:\n")
        json.dump(topics, f, indent=2)
        f.write("\n\nGenerated Clips:\n")
        json.dump(clips, f, indent=2)
    logger.info(f"Debug information saved to {debug_file}")

def upload_to_s3(file_path, config):
    logger.debug(f"Uploading file to S3: {file_path}")
    command = f"{config['aws_cli_path']} s3 cp {file_path} s3://{config['s3_bucket']}/public/{os.path.basename(file_path)}"
    subprocess.run(command, shell=True, check=True)
    logger.info(f"File uploaded successfully to S3: {file_path}")

def get_s3_presigned_url(file_name, config):
    logger.debug(f"Getting presigned URL for file: {file_name}")
    command = f"{config['aws_cli_path']} s3 presign s3://{config['s3_bucket']}/public/{file_name}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
    presigned_url = result.stdout.strip()
    logger.info(f"Presigned URL generated: {presigned_url}")
    return presigned_url

def create_zip_of_processed_files(output_folder):
    logger.info(f"Creating zip file for folder: {output_folder}")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
        temp_zip_path = temp_zip.name

    with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_folder)
                zipf.write(file_path, arcname)
                logger.debug(f"Added file to zip: {arcname}")

    logger.info(f"Zip file created: {temp_zip_path}")
    return temp_zip_path

def get_transcription_goal(goal: str = Form(...)) -> TranscriptionGoal:
    try:
        return TranscriptionGoal(goal)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid transcription goal")

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
        time.sleep(5)  # Use time.sleep instead 

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
    response = requests.post(config['anthropic_api_url'], headers=headers, json=data)
    logger.debug(f"Anthropic API response: {response.text}")
    return response.json()['content'][0]['text']

def create_media_clips(transcript, content, source_file, dest_folder, goal, config):
    logger.debug(f"Creating media clips for goal: {goal.value}")
    topic_extraction_message = f"""
    Based on the following {goal.value.replace('_', ' ')}:
    {content}

    Extract each of the main topics or segments discussed.

    For each topic/segment, provide:
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
        "model": config['anthropic_model'],
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": topic_extraction_message}
        ]
    }
    topic_response = requests.post(config['anthropic_api_url'], headers=headers, json=topic_extraction_data)
    topic_text = topic_response.json()['content'][0]['text']
    logger.debug(f"Full AI response for topic extraction:\n{topic_text}")

    try:
        topics = json.loads(topic_text)
    except json.JSONDecodeError:
        topic_pattern = r'\{\s*"title":\s*"([^"]+)",\s*"keywords":\s*\[((?:[^]]+))\]\s*\}'  
        matches = re.findall(topic_pattern, topic_text)
        topics = [{"title": title, "keywords": [k.strip(' "') for k in keywords.split(',')]} for title, keywords in matches]

    if not topics:
        raise ValueError("Failed to extract topics from the AI response")

    clip_generation_message = f"""
    For each of the following topics/segments, find the most relevant part in the transcript:
    {json.dumps(topics)}

    Transcript:
    {json.dumps(transcript)}

    For each topic/segment:
    1. Find the part that best represents the topic/segment.
    2. Aim for a clip duration of 2-5 minutes, but prioritize capturing the complete discussion or segment.
    3. If the relevant content exceeds 5 minutes, include it entirely to avoid cutting off important information.
    4. Ensure that the segment captures complete thoughts and ideas. Do not cut off in the middle of a sentence or a speaker's point.
    5. It's better to include slightly more content than to risk cutting off important information.

    Provide the results as a JSON array of objects, each containing:
    - title: The topic/segment title
    - start: Start time of the clip (in seconds)
    - end: End time of the clip (in seconds)

    The clips can overlap if necessary to capture complete discussions or segments.
    """

    clip_generation_data = {
        "model": config['anthropic_model'],
        "max_tokens": 2000,
        "messages": [
            {"role": "user", "content": clip_generation_message}
        ]
    }

    clip_response = requests.post(config['anthropic_api_url'], headers=headers, json=clip_generation_data)
    clip_text = clip_response.json()['content'][0]['text']
    logger.debug(f"Full AI response for clip generation:\n{clip_text}")

    try:
        clips = json.loads(clip_text)
    except json.JSONDecodeError:
        clip_pattern = r'\{\s*"title":\s*"([^"]+)",\s*"start":\s*(\d+(?:\.\d+)?),\s*"end":\s*(\d+(?:\.\d+)?)\s*\}'
        matches = re.findall(clip_pattern, clip_text)
        clips = [{"title": title, "start": float(start), "end": float(end)} for title, start, end in matches]

    if not clips:
        raise ValueError("Failed to extract clip information from the AI response")

    ffmpeg_commands = []
    for clip in clips:
        safe_title = ''.join(c for c in clip['title'] if c.isalnum() or c in (' ', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        output_file = os.path.join(dest_folder, f"{safe_title}{os.path.splitext(source_file)[1]}")
        start_time = clip['start']
        end_time = clip['end']
        buffer = 0.5
        start_time = max(0, start_time - buffer)
        end_time += buffer
        command = f"/opt/homebrew/bin/ffmpeg -i {source_file} -ss {start_time:.2f} -to {end_time:.2f} -y -c copy {output_file}"
        ffmpeg_commands.append(command)

    logger.debug(f"Generated FFmpeg commands: {ffmpeg_commands}")
    return ' && '.join(ffmpeg_commands), topics, clips

def execute_ffmpeg_commands(commands):
    logger.debug(f"Executing FFmpeg commands: {commands}")
    for command in commands.split('&&'):
        logger.debug(f"Executing command: {command.strip()}")
        subprocess.run(command.strip(), shell=True, check=True)
    logger.info("All FFmpeg commands executed successfully")

async def process_media(media_file: str, goal: TranscriptionGoal):
    global processing_status
    try:
        update_processing_status("processing", 0, "Starting transcription process")
        logger.info(f"Processing started for {media_file} with goal {goal}")

        # Use asyncio.to_thread for potentially blocking operations
        update_processing_status("processing", 10, "Uploading file to S3")
        await asyncio.to_thread(upload_to_s3, media_file, config)

        presigned_url = await asyncio.to_thread(get_s3_presigned_url, os.path.basename(media_file), config)
        update_processing_status("processing", 20, "Generating presigned URL")

        prediction = await asyncio.to_thread(start_transcription, presigned_url, config)
        update_processing_status("processing", 30, "Starting transcription")

        transcript = await asyncio.to_thread(get_transcription_result, prediction['urls']['get'], config)
        update_processing_status("processing", 40, "Processing transcription")

        # Save transcription to file
        output_name = os.path.splitext(os.path.basename(media_file))[0]
        output_folder = os.path.join(os.path.dirname(media_file), output_name)
        os.makedirs(output_folder, exist_ok=True)
        transcription_file = os.path.join(output_folder, f"{output_name}_transcription.txt")
        with open(transcription_file, 'w') as f:
            for segment in transcript:
                f.write(f"{segment['start']} - {segment['end']}: {segment['text']}\n")
        logger.info(f"Transcription saved to {transcription_file}")

        content = await asyncio.to_thread(generate_content, transcript, goal, config)
        update_processing_status("processing", 60, f"Generating {goal.value.replace('_', ' ')}")

        output_file = os.path.join(output_folder, f"{output_name}_{goal.value}.md")
        with open(output_file, 'w') as f:
            f.write(content)
        update_processing_status("processing", 70, "Saving generated content")

        ffmpeg_commands, topics, clips = await asyncio.to_thread(create_media_clips, transcript, content, media_file, output_folder, goal, config)
        update_processing_status("processing", 80, "Creating media clips")

        await asyncio.to_thread(save_debug_info, output_folder, content, topics, clips)
        update_processing_status("processing", 90, "Saving debug information")

        await asyncio.to_thread(execute_ffmpeg_commands, ffmpeg_commands)
        update_processing_status("processing", 95, "Executing FFmpeg commands")

        zip_file_path = await asyncio.to_thread(create_zip_of_processed_files, output_folder)
        update_processing_status("processing", 98, "Creating download package")

        update_processing_status("completed", 100, "Process complete")
        logger.info(f"Processing completed for {media_file}")

        return zip_file_path

    except Exception as e:
        logger.error(f"An error occurred while processing {media_file}: {str(e)}", exc_info=True)
        update_processing_status("error", 0, f"Error: {str(e)}")
        return None

    finally:
        if os.path.exists(media_file):
            os.remove(media_file)
            logger.info(f"Temporary file {media_file} removed")


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    goal: TranscriptionGoal = Depends(get_transcription_goal),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    global zip_file_path
    file_location = f"/tmp/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
    
    update_processing_status("processing", 0, "Starting processing")
    background_tasks.add_task(process_and_set_zip_path, file_location, goal)
    return {"message": "File uploaded successfully. Processing started."}

async def process_and_set_zip_path(file_location: str, goal: TranscriptionGoal):
    global zip_file_path
    zip_file_path = await process_media(file_location, goal)

@app.get("/status")
async def get_status():
    global processing_status
    if processing_status is None:
        return ProcessingStatus(status="idle", progress=0, message="")
    return processing_status

@app.get("/download")
async def download_processed_files():
    global zip_file_path
    logger.info(f"Download requested. Zip file path: {zip_file_path}")
    if zip_file_path and os.path.exists(zip_file_path):
        try:
            logger.info(f"Sending file: {zip_file_path}")
            return FileResponse(
                zip_file_path,
                media_type='application/zip',
                filename="processed_files.zip",
                headers={"Content-Disposition": "attachment; filename=processed_files.zip"}
            )
        finally:
            # Schedule the removal of the temporary file
            asyncio.create_task(remove_temp_file(zip_file_path))
    logger.error("Processed files not available")
    return {"error": "Processed files not available"}

async def remove_temp_file(file_path):
    await asyncio.sleep(60)  # Wait for 60 seconds to ensure the file has been sent
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Temporary zip file removed: {file_path}")

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = f"/tmp/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    return {"error": "File not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
