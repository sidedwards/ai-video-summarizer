from enum import Enum

class TranscriptionGoal(Enum):
    MEETING_MINUTES = "meeting_minutes"
    PODCAST_SUMMARY = "podcast_summary"
    LECTURE_NOTES = "lecture_notes"
    INTERVIEW_HIGHLIGHTS = "interview_highlights"
    GENERAL_TRANSCRIPTION = "general_transcription"