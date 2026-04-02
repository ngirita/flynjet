import os
import hashlib
from django.utils import timezone
from django.conf import settings

def generate_document_number(prefix='DOC'):
    """Generate unique document number"""
    import random
    import string
    timestamp = timezone.now().strftime('%Y%m')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{timestamp}{random_str}"

def get_file_size(file):
    """Get file size in bytes"""
    if hasattr(file, 'size'):
        return file.size
    elif hasattr(file, 'tell') and hasattr(file, 'seek'):
        pos = file.tell()
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(pos)
        return size
    return 0

def calculate_file_hash(file):
    """Calculate SHA-256 hash of file"""
    sha256 = hashlib.sha256()
    
    if hasattr(file, 'read'):
        for chunk in iter(lambda: file.read(8192), b''):
            sha256.update(chunk)
        file.seek(0)
        return sha256.hexdigest()
    
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    
    return sha256.hexdigest()

def verify_file_hash(file, expected_hash):
    """Verify file hash"""
    actual_hash = calculate_file_hash(file)
    return actual_hash == expected_hash

def get_file_extension(filename):
    """Get file extension"""
    return os.path.splitext(filename)[1].lower()

def is_allowed_file_type(filename, allowed_types):
    """Check if file type is allowed"""
    ext = get_file_extension(filename)
    return ext in allowed_types

def format_file_size(size_bytes):
    """Format file size human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def create_archive_filename(document):
    """Generate archive filename"""
    return f"{document.document_number}_{document.created_at.strftime('%Y%m%d')}.pdf"

def get_document_expiry_date(created_at, months=6):
    """Calculate document expiry date"""
    return created_at + timezone.timedelta(days=30 * months)

def generate_access_token():
    """Generate secure access token"""
    import uuid
    return uuid.uuid4()

def verify_signature(data, signature, secret=None):
    """Verify HMAC signature"""
    import hmac
    import hashlib
    
    if secret is None:
        secret = settings.SECRET_KEY.encode()
    
    expected = hmac.new(
        secret,
        data.encode() if isinstance(data, str) else data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

def compress_pdf(input_file, output_file, quality='medium'):
    """Compress PDF file"""
    from PyPDF2 import PdfReader, PdfWriter
    
    reader = PdfReader(input_file)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    # Set compression
    if quality == 'high':
        writer.compress_content_streams = True
    
    with open(output_file, 'wb') as f:
        writer.write(f)
    
    return output_file

def merge_pdfs(pdf_files, output_file):
    """Merge multiple PDFs"""
    from PyPDF2 import PdfMerger
    
    merger = PdfMerger()
    
    for pdf in pdf_files:
        merger.append(pdf)
    
    merger.write(output_file)
    merger.close()
    
    return output_file

def add_watermark(input_file, output_file, watermark_text):
    """Add watermark to PDF"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from PyPDF2 import PdfReader, PdfWriter
    import io
    
    # Create watermark
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    c.setFont("Helvetica", 50)
    c.setFillColorRGB(0.5, 0.5, 0.5, 0.3)
    c.rotate(45)
    c.drawString(200, 200, watermark_text)
    c.save()
    
    packet.seek(0)
    watermark = PdfReader(packet)
    
    # Apply watermark
    reader = PdfReader(input_file)
    writer = PdfWriter()
    
    for page in reader.pages:
        page.merge_page(watermark.pages[0])
        writer.add_page(page)
    
    with open(output_file, 'wb') as f:
        writer.write(f)
    
    return output_file