from abc import ABC, abstractmethod
from typing import Optional
import logging
from io import BytesIO
from fpdf import FPDF
from docx import Document


logger = logging.getLogger(__name__)

class BaseExporter(ABC):
    @abstractmethod
    def export(self, content: str) -> bytes:
        """Convert the given text content into the target format and return it as bytes."""
        pass

    @abstractmethod 
    def get_extension(self) -> str:
        """Return the file extension (including the dot) for the export format."""
        pass

class MarkdownExporter(BaseExporter):
    def export(self, content: str) -> bytes:
        """Simply encode the markdown content as UTF-8 bytes."""
        try:
            return content.encode('utf-8')
        except Exception as e:
            logger.error(f"Error exporting to Markdown: {e}")
            raise

    def get_extension(self) -> str:
        return ".md"

class PDFExporter(BaseExporter):
    def __init__(self):
        if FPDF is None:
            raise ImportError("FPDF is required for PDF export. Please install it using 'pip install fpdf'")
        self.FPDF = FPDF

    def export(self, content: str) -> bytes:
        """Convert content to PDF format using FPDF."""
        try:
            pdf = self.FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=12)
            
            # Write content line by line
            for line in content.splitlines():
                # Encode to handle special characters
                encoded_line = line.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(0, 10, txt=encoded_line, ln=True)
            
            return pdf.output(dest="S").encode('latin1')
        except Exception as e:
            logger.error(f"Error exporting to PDF: {e}")
            raise

    def get_extension(self) -> str:
        return ".pdf"

class DocxExporter(BaseExporter):
    def __init__(self):
        if Document is None:
            raise ImportError("python-docx is required for DOCX export. Please install it using 'pip install python-docx'")
        self.Document = Document
        self.BytesIO = BytesIO

    def export(self, content: str) -> bytes:
        """Convert content to DOCX format using python-docx."""
        try:
            document = self.Document()
            
            # Add content as paragraphs
            for line in content.splitlines():
                if line.strip():  # Only add non-empty lines
                    document.add_paragraph(line)
            
            bio = self.BytesIO()
            document.save(bio)
            return bio.getvalue()
        except Exception as e:
            logger.error(f"Error exporting to DOCX: {e}")
            raise

    def get_extension(self) -> str:
        return ".docx"

def get_exporter(export_format: Optional[str] = None) -> BaseExporter:
    """Factory function to get the appropriate exporter based on format.
    
    Args:
        export_format: The desired export format (pdf, docx, or markdown)
        
    Returns:
        An instance of the appropriate exporter class
        
    Raises:
        ValueError: If an invalid export format is specified
    """
    # Trim extra whitespace and convert to lowercase
    format_lower = (export_format or "markdown").strip().lower()
    logger.debug(f"Initializing exporter for format: '{format_lower}'")
    
    try:
        if format_lower == "pdf":
            logger.info("Creating PDF exporter")
            try:
                exporter = PDFExporter()
                logger.info("PDF exporter created successfully")
                return exporter
            except ImportError as e:
                logger.error(f"Failed to create PDF exporter due to missing dependencies: {e}")
                logger.warning("Falling back to markdown export")
                return MarkdownExporter()
        elif format_lower in ["docx", "doc"]:  # Support both docx and doc
            logger.info("Creating DOCX exporter")
            try:
                exporter = DocxExporter()
                logger.info("DOCX exporter created successfully")
                return exporter
            except ImportError as e:
                logger.error(f"Failed to create DOCX exporter due to missing dependencies: {e}")
                logger.warning("Falling back to markdown export")
                return MarkdownExporter()
        elif format_lower in ["markdown", "md"]:  # Support both markdown and md
            logger.info("Creating Markdown exporter")
            return MarkdownExporter()
        else:
            logger.warning(f"Unknown export format '{format_lower}', falling back to markdown")
            return MarkdownExporter()
    except Exception as e:
        logger.error(f"Unexpected error initializing {format_lower} exporter: {e}")
        logger.warning("Falling back to markdown export")
        return MarkdownExporter() 