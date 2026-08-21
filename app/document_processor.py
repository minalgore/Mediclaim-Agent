from pathlib import Path
from typing import Union


class DocumentProcessor:
    """
    Extract text from supported medical claim documents.

    Supported formats:
        - TXT
        - PDF
        - PNG
        - JPG / JPEG
        - TIFF
        - BMP

    The processor only extracts text.
    PII/PHI redaction is handled separately by PIIRedactor.
    """

    SUPPORTED_TEXT_FORMATS = {
        ".txt",
    }

    SUPPORTED_PDF_FORMATS = {
        ".pdf",
    }

    SUPPORTED_IMAGE_FORMATS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
        ".bmp",
    }

    def __init__(self):
        pass

    # =========================================================
    # Main entry point
    # =========================================================

    def extract_text(
        self,
        path: Union[str, Path],
    ) -> str:
        """
        Extract text from a medical document.

        Args:
            path:
                Path to the document.

        Returns:
            Extracted text as a string.

        Raises:
            FileNotFoundError:
                If the document does not exist.

            ValueError:
                If the file format is unsupported.
        """

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                "Document not found: {}".format(file_path)
            )

        if not file_path.is_file():
            raise ValueError(
                "Path is not a file: {}".format(file_path)
            )

        suffix = file_path.suffix.lower()

        if suffix in self.SUPPORTED_TEXT_FORMATS:
            return self._extract_text_file(file_path)

        if suffix in self.SUPPORTED_PDF_FORMATS:
            return self._extract_pdf(file_path)

        if suffix in self.SUPPORTED_IMAGE_FORMATS:
            return self._extract_image(file_path)

        raise ValueError(
            "Unsupported document type: {}".format(
                suffix or "[no extension]"
            )
        )

    # =========================================================
    # TXT extraction
    # =========================================================

    def _extract_text_file(
        self,
        file_path: Path,
    ) -> str:
        """
        Read a UTF-8 text document.
        """

        return file_path.read_text(
            encoding="utf-8"
        )

    # =========================================================
    # PDF extraction
    # =========================================================

    def _extract_pdf(
        self,
        file_path: Path,
    ) -> str:
        """
        Extract text from all pages of a PDF.

        Uses PyMuPDF (fitz).
        """

        try:
            import fitz
        except ImportError:
            raise ImportError(
                "PyMuPDF is required for PDF processing. "
                "Install it with: pip install PyMuPDF"
            )

        document = fitz.open(
            str(file_path)
        )

        try:
            pages = []

            for page in document:
                page_text = page.get_text()

                if page_text:
                    pages.append(page_text)

            return "\n".join(pages)

        finally:
            document.close()

    # =========================================================
    # Image extraction
    # =========================================================

    def _extract_image(
        self,
        file_path: Path,
    ) -> str:
        """
        Extract text from an image using OCR.

        Uses:
            Pillow
            pytesseract
            system Tesseract OCR
        """

        try:
            from PIL import Image
        except ImportError:
            raise ImportError(
                "Pillow is required for image processing. "
                "Install it with: pip install Pillow"
            )

        try:
            import pytesseract
        except ImportError:
            raise ImportError(
                "pytesseract is required for image OCR. "
                "Install it with: pip install pytesseract"
            )

        image = Image.open(
            str(file_path)
        )

        try:
            text = pytesseract.image_to_string(
                image
            )
        except Exception as exc:
            raise RuntimeError(
                "OCR processing failed: {}".format(
                    exc
                )
            )

        return text

    # =========================================================
    # Supported format check
    # =========================================================

    def is_supported(
        self,
        path: Union[str, Path],
    ) -> bool:
        """
        Check whether a document format is supported.
        """

        suffix = Path(path).suffix.lower()

        return (
            suffix in self.SUPPORTED_TEXT_FORMATS
            or suffix in self.SUPPORTED_PDF_FORMATS
            or suffix in self.SUPPORTED_IMAGE_FORMATS
        )

    # =========================================================
    # File type
    # =========================================================

    def get_document_type(
        self,
        path: Union[str, Path],
    ) -> str:
        """
        Return a normalized document type.

        Returns:
            TXT
            PDF
            IMAGE
            UNKNOWN
        """

        suffix = Path(path).suffix.lower()

        if suffix in self.SUPPORTED_TEXT_FORMATS:
            return "TXT"

        if suffix in self.SUPPORTED_PDF_FORMATS:
            return "PDF"

        if suffix in self.SUPPORTED_IMAGE_FORMATS:
            return "IMAGE"

        return "UNKNOWN"


def process_document(
    content: bytes,
    filename: str = "document",
):
    """
    Process an uploaded medical document.

    This is the API-facing helper used by app.api.

    Steps:
        1. Determine document type from filename.
        2. Extract text from uploaded bytes.
        3. Redact PII/PHI.
        4. Return a structured document result.
    """

    from tempfile import NamedTemporaryFile

    from app.pii_redactor import PIIRedactor

    filename = filename or "document"

    suffix = Path(filename).suffix.lower()

    if not suffix:
        suffix = ".txt"

    processor = DocumentProcessor()

    if suffix not in (
        processor.SUPPORTED_TEXT_FORMATS
        | processor.SUPPORTED_PDF_FORMATS
        | processor.SUPPORTED_IMAGE_FORMATS
    ):
        raise ValueError(
            "Unsupported document type: {}".format(
                suffix
            )
        )

    temporary_path = None

    try:
        with NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:

            temp_file.write(content)
            temp_file.flush()

            temporary_path = Path(
                temp_file.name
            )

        extracted_text = processor.extract_text(
            temporary_path
        )

        redactor = PIIRedactor()

        redaction_result = (
            redactor.redact_text(
                extracted_text
            )
        )

        document_type = (
            processor.get_document_type(
                temporary_path
            )
        )

        return {
            "filename": filename,
            "document_type": document_type,
            "extracted_text": extracted_text,
            "sanitized_text": redaction_result.text,
            "detected_entities": getattr(
                redaction_result,
                "detected_entities",
                [],
            ),
            "redaction_count": getattr(
                redaction_result,
                "redaction_count",
                0,
            ),
        }

    finally:

        if temporary_path is not None:

            try:
                temporary_path.unlink()
            except OSError:
                pass


def process_document(
    content: bytes,
    filename: str = "document",
):
    """
    Process an uploaded medical document.

    The API provides document contents as bytes.
    This helper temporarily stores the file so that
    DocumentProcessor can use its existing extraction
    pipeline.

    PII/PHI is redacted after text extraction.
    """

    from tempfile import NamedTemporaryFile

    from app.models import DocumentProcessingResult
    from app.pii_redactor import PIIRedactor

    filename = filename or "document"

    suffix = Path(filename).suffix.lower()

    if not suffix:
        suffix = ".txt"

    processor = DocumentProcessor()

    supported_formats = (
        processor.SUPPORTED_TEXT_FORMATS
        | processor.SUPPORTED_PDF_FORMATS
        | processor.SUPPORTED_IMAGE_FORMATS
    )

    if suffix not in supported_formats:
        raise ValueError(
            "Unsupported document type: {}".format(
                suffix
            )
        )

    temporary_path = None

    try:
        with NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:

            temp_file.write(content)
            temp_file.flush()

            temporary_path = Path(
                temp_file.name
            )

        # ---------------------------------------------
        # Extract text
        # ---------------------------------------------

        extracted_text = processor.extract_text(
            temporary_path
        )

        # ---------------------------------------------
        # PII / PHI redaction
        # ---------------------------------------------

        redactor = PIIRedactor()

        redaction_result = (
            redactor.redact_text(
                extracted_text
            )
        )

        # ---------------------------------------------
        # Document type
        # ---------------------------------------------

        document_type = (
            processor.get_document_type(
                temporary_path
            )
        )

        # ---------------------------------------------
        # Build API response
        # ---------------------------------------------

        return DocumentProcessingResult(
            filename=filename,
            document_type=document_type,
            extracted_text=extracted_text,
            sanitized_text=redaction_result.text,
            detected_entities=getattr(
                redaction_result,
                "detected_entities",
                [],
            ),
            redaction_count=getattr(
                redaction_result,
                "redaction_count",
                0,
            ),
        )

    finally:

        if temporary_path is not None:

            try:
                temporary_path.unlink()

            except OSError:
                pass