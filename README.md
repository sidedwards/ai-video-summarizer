# AI Meeting Transcriber and Summarizer

This project automates the process of transcribing meeting recordings, generating detailed minutes, and creating video clips for each discussion topic using AI technologies.

## Tech Stack

- Python 3.8+
- AWS S3 for file storage
- Replicate API for running WhisperX (transcription)
- Anthropic's Claude API for generating meeting minutes and video clip commands
- FFmpeg for video processing

## Features

- Transcribe meeting recordings using WhisperX
- Generate detailed meeting minutes using Claude AI
- Create video clips for each main discussion topic
- Upload and manage files using AWS S3

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.8 or higher
- [AWS CLI](https://aws.amazon.com/cli/)
- [FFmpeg](https://ffmpeg.org/)

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/sidedwards/ai-meeting-transcriber.git
   cd ai-meeting-transcriber
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your configuration:
   - Copy `config/config-example.yaml` to `config/config.yaml`
   - Edit `config/config.yaml` with your API keys and preferences

5. Obtain necessary API keys and credentials:
   - AWS: Set up an AWS account and configure the AWS CLI with your credentials
   - Replicate: Sign up at [replicate.com](https://replicate.com) and get your API key
   - Anthropic: Apply for API access at [anthropic.com](https://www.anthropic.com)

## WhisperX

This project uses WhisperX, an advanced version of OpenAI's Whisper model, for transcription. WhisperX offers:

- Accelerated transcription
- Advanced speaker diarization
- Improved accuracy in speaker segmentation

The WhisperX model is run via the Replicate API, based on https://github.com/sidedwards/whisperx.

## Usage

Run the main script:

```
python src/main.py
```

Follow the prompts to select a video file. The script will:
1. Upload the file to S3
2. Transcribe the audio
3. Generate meeting minutes
4. Create video clips for each main discussion topic

## Configuration

Edit `config/config.yaml` to set:

- AWS CLI path and S3 bucket name
- Replicate API key and model version
- Anthropic API key and model choice
- Other customizable parameters

## Note

Ensure that you have the necessary permissions and quotas for the APIs you're using. Some services may have usage limits or require approval for higher volumes.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
