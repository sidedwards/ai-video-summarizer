import os
import subprocess
import asyncio
import zipfile
import tempfile


from fastapi import (
    FastAPI,
    File,
    UploadFile,
    Form,
    Depends,
    BackgroundTasks
)
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai_jobs import (
    create_media_clips,
    generate_content,
    get_transcription_result,
    start_transcription,
)
from s3 import get_s3_presigned_url, upload_to_s3
from log import logger, save_debug_info
from transcription_goal import TranscriptionGoal
from utils import load_config



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

class ProcessingStatus(BaseModel):
    status: str
    progress: int
    message: str

def update_processing_status(status: str, progress: int, message: str):
    global processing_status
    processing_status = ProcessingStatus(status=status, progress=progress, message=message)
    logger.info(f"Status Update: {status} - Progress: {progress}% - Message: {message}")
    return processing_status

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
