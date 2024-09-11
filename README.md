# AI Video Summarizer

Transcribe, summarize, and create smart clips from video and audio content.

## Features

- **Transcription**: Transcribe audio using WhisperX
- **Smart Summarization**: Generate concise summaries of video content, tailored to different purposes:
  - Meeting Minutes
  - Podcast Summaries
  - Lecture Notes
  - Interview Highlights
  - General Content Summaries
- **Intelligent Clip Creation**: Automatically create clips of key moments and topics discussed in the video.
- **Multi-format Support**: Process various video and audio file formats.
- **Cloud Integration**: Utilizes AWS S3 for efficient file handling and processing.

## Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate permissions
- FFmpeg installed on your system

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/sidedwards/ai-video-summarizer.git
   cd ai-video-summarizer
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

## Usage

Run the main script:

```
python src/main.py
```

Follow the prompts to select a video file and choose the type of summary you want to generate.

## Configuration

Edit `config/config.yaml` to set:

- AWS CLI path and S3 bucket name
- Replicate API key and model version
- Anthropic API key and model choice
- Other customizable parameters

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)

## Acknowledgements

### WhisperX

This project uses WhisperX, an advanced version of OpenAI's Whisper model, for transcription. WhisperX offers:

- Accelerated transcription
- Advanced speaker diarization
- Improved accuracy in speaker segmentation

The WhisperX model is run via the Replicate API, based on https://github.com/sidedwards/whisperx.