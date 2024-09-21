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
- Node.js and npm (for running the frontend GUI)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/sidedwards/ai-video-summarizer.git
   cd ai-video-summarizer
   ```

2. Set up the backend:
   - Create and activate a virtual environment:
     ```
     python -m venv .venv
     source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
     ```
   - Install the required dependencies:
     ```
     pip install -r requirements.txt
     ```
   - Set up your configuration:
     - Copy `config/config-example.yaml` to `config/config.yaml`
     - Edit `config/config.yaml` with your API keys and preferences

3. Set up the frontend (optional, for GUI usage):
   - Navigate to the frontend directory:
     ```
     cd frontend
     ```
   - Install the required dependencies:
     ```
     npm install
     ```

## Usage

### CLI

1. Run the CLI script:
   ```
   python backend/cli.py
   ```
2. Follow the prompts to select a video file and choose the type of summary you want to generate.
3. The generated summary files will be saved in a directory named after the input video file.

### GUI

1. Start the backend server:
   - Run the backend server:
     ```
     python backend/server.py
     ```
2. Start the frontend development server:
   - In a new terminal window, navigate to the frontend directory:
     ```
     cd frontend
     ```
   - Run the frontend development server:
     ```
     npm run dev
     ```
3. Open your web browser and navigate to `http://localhost:5173` to access the AI Video Summarizer GUI.
4. Use the web interface to upload a video file, select the desired summary type, and start the processing.
5. Once the processing is complete, you can download the generated summary files as a zip archive.

## Configuration

Edit `config/config.yaml` to set:

- AWS CLI path and S3 bucket name
- Replicate API key and model version
- Anthropic API key and model choice
- Other customizable parameters

## Roadmap

- [x] Web-based GUI
- [x] Basic CLI
- [ ] More LLM options
- [ ] Export options for various document formats (PDF, DOCX, etc.)

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