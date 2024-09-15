import os
import logging
from logging.handlers import RotatingFileHandler
import json
import re
import requests
import time
import subprocess
from utils import prompt_for_goal, prompt_for_media_file, load_config
from transcription_goal import TranscriptionGoal

# Set up logging
log_file = 'debug.log'
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        RotatingFileHandler(log_file, maxBytes=10000000, backupCount=5),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

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
    # Use raw string literals or replace single backslashes with double backslashes
    file_path = r"{}".format(file_path)
    s3_destination = f"s3://{config['s3_bucket']}/public/{os.path.basename(file_path)}"
    command = f"{config['aws_cli_path']} s3 cp \"{file_path}\" \"{s3_destination}\""
    logger.debug(f"S3 upload command: {command}")
    
    # Check if the file exists before attempting to upload
    if not os.path.isfile(file_path):
        logger.error(f"The file does not exist: {file_path}")
        return
    
    try:
        subprocess.run(command, shell=True, check=True)
        logger.info(f"File uploaded successfully to S3: {file_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to upload file to S3: {e}")
        raise


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
    
    # Log the full AI response
    logger.debug(f"Full AI response for content generation:\n{response.json()['content'][0]['text']}")
    
    return response.json()['content'][0]['text']

def create_media_clips(transcript, content, source_file, dest_folder, goal, config):
    logger.debug(f"Creating media clips for goal: {goal.value}")
    
    # Modify the topic extraction message based on the goal
    topic_extraction_message = f"""
    Based on the following {goal.value.replace('_', ' ')}:
    {content}

    Extract the main topics or segments discussed.

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
    
    # Log the full AI response for topic extraction
    logger.debug(f"Full AI response for topic extraction:\n{topic_text}")
    
    # Try to extract JSON from the response
    try:
        topics = json.loads(topic_text)
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract the relevant information using regex
        topic_pattern = r'\{\s*"title":\s*"([^"]+)",\s*"keywords":\s*\[((?:[^]]+))\]\s*\}'
        matches = re.findall(topic_pattern, topic_text)
        topics = [{"title": title, "keywords": [k.strip(' "') for k in keywords.split(',')]} for title, keywords in matches]

    if not topics:
        raise ValueError("Failed to extract topics from the AI response")

    # Now, let's find relevant segments for each topic
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

    # Log the full AI response for clip generation
    logger.debug(f"Full AI response for clip generation:\n{clip_text}")

    # Try to extract JSON from the response
    try:
        clips = json.loads(clip_text)
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract the relevant information using regex
        clip_pattern = r'\{\s*"title":\s*"([^"]+)",\s*"start":\s*(\d+(?:\.\d+)?),\s*"end":\s*(\d+(?:\.\d+)?)\s*\}'
        matches = re.findall(clip_pattern, clip_text)
        clips = [{"title": title, "start": float(start), "end": float(end)} for title, start, end in matches]

    if not clips:
        raise ValueError("Failed to extract clip information from the AI response")

    def find_sentence_boundary(transcript, time, direction):
        """
        Find the nearest sentence boundary in the given direction.
        direction should be 1 for forward search, -1 for backward search.
        """
        sentence_end_punctuation = '.!?'
        for segment in sorted(transcript, key=lambda x: x['start'], reverse=(direction < 0)):
            if (direction > 0 and segment['start'] >= time) or (direction < 0 and segment['end'] <= time):
                text = segment['text']
                if direction > 0:
                    if any(text.strip().endswith(p) for p in sentence_end_punctuation):
                        return segment['end']
                else:
                    if any(text.strip().endswith(p) for p in sentence_end_punctuation):
                        return segment['start']
        return time  # If no boundary found, return original time

    # Generate FFmpeg commands with intelligent boundaries
    ffmpeg_commands = []
    for clip in clips:
        safe_title = ''.join(c for c in clip['title'] if c.isalnum() or c in (' ', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        output_file = os.path.join(dest_folder, f"{safe_title}{os.path.splitext(source_file)[1]}")
        
        # Find nearest sentence boundaries
        start_time = find_sentence_boundary(transcript, clip['start'], -1)
        end_time = find_sentence_boundary(transcript, clip['end'], 1)
        
        # Add a small buffer (e.g., 0.5 seconds) to account for any slight misalignments
        buffer = 0.5
        start_time = max(0, start_time - buffer)
        end_time += buffer

        command = f"ffmpeg -i {source_file} -ss {start_time:.2f} -to {end_time:.2f} -y -c copy {output_file}"
        ffmpeg_commands.append(command)

    logger.debug(f"Generated FFmpeg commands: {ffmpeg_commands}")
    return ' && '.join(ffmpeg_commands), topics, clips

# Generate FFmpeg commands
def execute_ffmpeg_commands(commands):
    logger.debug(f"Executing FFmpeg commands: {commands}")
    for command in commands.split('&&'):
        logger.debug(f"Executing command: {command.strip()}")
        subprocess.run(command.strip(), shell=True, check=True)
    logger.info("All FFmpeg commands executed successfully")

def transcribe_video(media_file, goal=TranscriptionGoal.GENERAL_TRANSCRIPTION, progress_callback=None):
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
        ffmpeg_commands, topics, clips = create_media_clips(transcript, content, media_file, output_folder, goal, config)
        
        # Save debug information
        save_debug_info(output_folder, content, topics, clips)

        execute_ffmpeg_commands(ffmpeg_commands)
        
        if progress_callback:
            progress_callback("Process complete", 100)
        
        logger.info("Main process completed successfully")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        raise


def download_youtube_video(youtube_url):
    # Extract the video ID from the YouTube URL
    video_id = youtube_url.split('v=')[1]
    # Define the output template for the downloaded video using the video ID
    output_template = os.path.join('downloads', f'{video_id}.%(ext)s')

    # Ensure the downloads directory exists
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # Define the command to download the video using yt-dlp
    command = [
        'yt-dlp',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        '--output', output_template,
        youtube_url
    ]

    # Run the yt-dlp command
    result = subprocess.run(command, capture_output=True, text=True)
    # Check for errors in stderr
    if result.stderr:
        print(result.stderr)

    # Check if the file with the video ID already exists
    downloaded_file_path = output_template.replace('%(ext)s', 'mp4')  # Assuming mp4 is the extension
    if os.path.exists(downloaded_file_path):
        return downloaded_file_path
    else:
        # If the file path couldn't be found, raise an error
        raise Exception("The video could not be downloaded or the file path could not be found.")

        

def main():
    choice = input("Enter '1' to upload a local file or '2' to transcribe a YouTube video: ")
    if choice == '1':
        media_file = prompt_for_media_file()
    elif choice == '2':
        youtube_url = input("Enter the full YouTube video URL: ")
        media_file = download_youtube_video(youtube_url)
    else:
        print("Invalid choice. Exiting.")
        return

    if media_file:
        logger.info(f"Media file selected: {media_file}")
        goal = prompt_for_goal()
        logger.info(f"Transcription goal selected: {goal.value}")
        transcribe_video(media_file, goal)
    else:
        logger.warning("No media file selected. Exiting.")


if __name__ == "__main__":
    main()