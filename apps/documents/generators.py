import os
import io
import hashlib
from datetime import datetime
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.files.base import ContentFile
import logging

# Initialize logger FIRST
logger = logging.getLogger(__name__)

# Try to import optional dependencies with fallbacks
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint not available - PDF generation will be limited")

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available - PDF generation will be limited")

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    logger.warning("qrcode not available - QR code generation will be disabled")

class DocumentGenerator:
    """Generate various documents (invoices, tickets, contracts)"""
    
    def __init__(self, document):
        self.document = document
        
        # Ensure content_data is a dictionary
        if hasattr(document, 'content_data'):
            if isinstance(document.content_data, dict):
                self.data = document.content_data
            else:
                # If it's not a dict, try to convert or use empty dict
                try:
                    import json
                    if isinstance(document.content_data, str):
                        self.data = json.loads(document.content_data)
                    else:
                        self.data = {}
                except:
                    self.data = {}
        else:
            self.data = {}
        
        # Clean the data - remove any Django form objects
        if isinstance(self.data, dict):
            cleaned_data = {}
            for key, value in self.data.items():
                # Skip Django form objects (they have has_changed attribute)
                if hasattr(value, 'has_changed'):
                    continue
                # Convert Django model instances to strings
                if hasattr(value, '_meta') and hasattr(value, '__dict__'):
                    try:
                        cleaned_data[key] = str(value)
                    except:
                        cleaned_data[key] = str(value)
                # Handle nested dictionaries
                elif isinstance(value, dict):
                    nested_cleaned = {}
                    for nested_key, nested_value in value.items():
                        if hasattr(nested_value, 'has_changed'):
                            continue
                        if hasattr(nested_value, '_meta'):
                            nested_cleaned[nested_key] = str(nested_value)
                        else:
                            nested_cleaned[nested_key] = nested_value
                    cleaned_data[key] = nested_cleaned
                # Handle lists
                elif isinstance(value, list):
                    cleaned_list = []
                    for item in value:
                        if hasattr(item, 'has_changed'):
                            continue
                        if hasattr(item, '_meta'):
                            cleaned_list.append(str(item))
                        else:
                            cleaned_list.append(item)
                    cleaned_data[key] = cleaned_list
                else:
                    cleaned_data[key] = value
            self.data = cleaned_data
        
        # Log for debugging
        if not self.data:
            logger.warning(f"No content_data found for document {self.document.document_number}")
        else:
            logger.info(f"Loaded {len(self.data)} data items for document {self.document.document_number}")
    
    def generate_pdf(self):
        """Generate PDF document"""
        if not REPORTLAB_AVAILABLE:
            logger.warning("ReportLab not installed - falling back to text generation")
            return self.generate_text()
        
        method_name = f"generate_{self.document.document_type}_pdf"
        method = getattr(self, method_name, self.generate_default_pdf)
        try:
            return method()
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return self.generate_text()
    
    def generate_text(self):
        """Fallback text document generation when PDF libraries aren't available"""
        buffer = io.StringIO()
        
        buffer.write(f"{'='*60}\n")
        buffer.write(f"FlynJet\n")
        buffer.write(f"{'='*60}\n\n")
        buffer.write(f"Document: {self.document.title}\n")
        buffer.write(f"Document Number: {self.document.document_number}\n")
        buffer.write(f"Date: {timezone.now().strftime('%B %d, %Y')}\n")
        buffer.write(f"{'-'*60}\n\n")
        
        # Safely iterate through data
        if isinstance(self.data, dict):
            for key, value in self.data.items():
                if hasattr(value, 'has_changed'):
                    continue
                if isinstance(value, dict):
                    buffer.write(f"\n{key}:\n")
                    for sub_key, sub_value in value.items():
                        if hasattr(sub_value, 'has_changed'):
                            continue
                        buffer.write(f"  {sub_key}: {sub_value}\n")
                elif isinstance(value, list):
                    buffer.write(f"\n{key}:\n")
                    for item in value:
                        if hasattr(item, 'has_changed'):
                            continue
                        if isinstance(item, dict):
                            for item_key, item_value in item.items():
                                if hasattr(item_value, 'has_changed'):
                                    continue
                                buffer.write(f"  {item_key}: {item_value}\n")
                        else:
                            buffer.write(f"  - {item}\n")
                else:
                    buffer.write(f"{key}: {value}\n")
        else:
            # If data is not a dict, just write the raw data
            buffer.write(f"Content Data: {self.data}\n")
        
        buffer.write(f"\n{'-'*60}\n")
        buffer.write(f"This document was generated automatically by FlynJet.\n")
        
        content = buffer.getvalue().encode('utf-8')
        return ContentFile(content, f"{self.document.document_number}.txt")
    
    def generate_default_pdf(self):
        """Default PDF generation method using ReportLab"""
        if not REPORTLAB_AVAILABLE:
            return self.generate_text()
        
        try:
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # Header
            p.setFont("Helvetica-Bold", 20)
            p.drawString(50, height - 50, "FlynJet")
            
            p.setFont("Helvetica", 12)
            p.drawString(50, height - 70, self.document.title)
            p.drawString(50, height - 85, f"Document: {self.document.document_number}")
            p.drawString(50, height - 100, f"Date: {timezone.now().strftime('%B %d, %Y')}")
            
            # Content
            y = height - 150
            p.setFont("Helvetica", 10)
            
            # Safely iterate through data
            if isinstance(self.data, dict):
                for key, value in self.data.items():
                    if hasattr(value, 'has_changed'):
                        continue
                    text = f"{key}: {value}"
                    # Truncate long text
                    if len(text) > 100:
                        text = text[:97] + "..."
                    p.drawString(50, y, text)
                    y -= 15
                    if y < 50:  # New page
                        p.showPage()
                        y = height - 50
            else:
                p.drawString(50, y, f"Content: {self.data}")
            
            p.save()
            buffer.seek(0)
            return ContentFile(buffer.getvalue(), f"{self.document.document_number}.pdf")
        except Exception as e:
            logger.error(f"Error in default PDF generation: {e}")
            return self.generate_text()
    
    def generate_invoice_pdf(self):
        """Generate professional invoice PDF"""
        if not REPORTLAB_AVAILABLE:
            return self.generate_text()
        
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Header
            story.append(Paragraph("FlynJet", title_style))
            story.append(Paragraph("INVOICE", heading_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Invoice Details - safe get with defaults
            due_date = self.data.get('due_date', 'N/A') if isinstance(self.data, dict) else 'N/A'
            booking_ref = self.data.get('booking_reference', 'N/A') if isinstance(self.data, dict) else 'N/A'
            
            invoice_data = [
                ["Invoice Number:", self.document.document_number],
                ["Date:", timezone.now().strftime('%B %d, %Y')],
                ["Due Date:", due_date],
                ["Booking Reference:", booking_ref],
            ]
            
            invoice_table = Table(invoice_data, colWidths=[1.5*inch, 3*inch])
            invoice_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(invoice_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Billing Information
            story.append(Paragraph("Bill To:", heading_style))
            
            customer_name = self.data.get('customer_name', 'N/A') if isinstance(self.data, dict) else 'N/A'
            customer_email = self.data.get('customer_email', 'N/A') if isinstance(self.data, dict) else 'N/A'
            customer_address = self.data.get('customer_address', 'N/A') if isinstance(self.data, dict) else 'N/A'
            
            billing_data = [
                [customer_name],
                [customer_email],
                [customer_address],
            ]
            billing_table = Table(billing_data, colWidths=[4.5*inch])
            billing_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
            ]))
            story.append(billing_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Items Table
            items_data = [["Description", "Quantity", "Unit Price", "Total"]]
            
            items = self.data.get('items', []) if isinstance(self.data, dict) else []
            for item in items:
                if isinstance(item, dict):
                    items_data.append([
                        item.get('description', ''),
                        str(item.get('quantity', 1)),
                        f"${item.get('unit_price', 0):.2f}",
                        f"${item.get('total', 0):.2f}"
                    ])
            
            # Totals
            subtotal = self.data.get('subtotal', 0) if isinstance(self.data, dict) else 0
            tax = self.data.get('tax', 0) if isinstance(self.data, dict) else 0
            total = self.data.get('total', 0) if isinstance(self.data, dict) else 0
            
            items_data.append(["", "", "Subtotal:", f"${subtotal:.2f}"])
            items_data.append(["", "", "Tax:", f"${tax:.2f}"])
            items_data.append(["", "", "Total:", f"${total:.2f}"])
            
            items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
            items_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -4), 1, colors.black),
                ('LINEBELOW', (0, -4), (-1, -4), 1, colors.black),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
            ]))
            story.append(items_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Payment Information
            story.append(Paragraph("Payment Information:", heading_style))
            
            payment_method = self.data.get('payment_method', 'N/A') if isinstance(self.data, dict) else 'N/A'
            transaction_id = self.data.get('transaction_id', 'N/A') if isinstance(self.data, dict) else 'N/A'
            payment_status = self.data.get('payment_status', 'N/A') if isinstance(self.data, dict) else 'N/A'
            
            payment_data = [
                ["Payment Method:", payment_method],
                ["Transaction ID:", transaction_id],
                ["Payment Status:", payment_status],
            ]
            payment_table = Table(payment_data, colWidths=[1.5*inch, 3*inch])
            payment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ]))
            story.append(payment_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Notes
            notes = self.data.get('notes') if isinstance(self.data, dict) else None
            if notes:
                story.append(Paragraph("Notes:", heading_style))
                story.append(Paragraph(notes, normal_style))
                story.append(Spacer(1, 0.2*inch))
            
            # Terms
            terms = self.data.get('terms') if isinstance(self.data, dict) else None
            if terms:
                story.append(Paragraph("Terms & Conditions:", heading_style))
                story.append(Paragraph(terms, normal_style))
            
            # Generate QR Code
            if QRCODE_AVAILABLE:
                try:
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr_data = f"https://flynjet.com/verify/{self.document.access_token}"
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    
                    # Save QR to buffer
                    qr_buffer = io.BytesIO()
                    qr_img.save(qr_buffer, format='PNG')
                    qr_buffer.seek(0)
                    
                    qr_platypus = Image(qr_buffer, width=1*inch, height=1*inch)
                    story.append(Spacer(1, 0.2*inch))
                    story.append(qr_platypus)
                except Exception as e:
                    logger.error(f"Error generating QR code: {e}")
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            return ContentFile(buffer.getvalue(), f"invoice_{self.document.document_number}.pdf")
            
        except Exception as e:
            logger.error(f"Error generating invoice PDF: {e}")
            return self.generate_text()
    
    def generate_ticket_pdf(self):
        """Generate e-ticket PDF"""
        if not REPORTLAB_AVAILABLE:
            return self.generate_text()
        
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            
            styles = getSampleStyleSheet()
            
            # Header
            story.append(Paragraph("FlynJet", styles['Title']))
            story.append(Paragraph("ELECTRONIC TICKET", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            
            # Ticket Information - safe get with defaults
            booking_ref = self.data.get('booking_reference', 'N/A') if isinstance(self.data, dict) else 'N/A'
            passenger_name = self.data.get('passenger_name', 'N/A') if isinstance(self.data, dict) else 'N/A'
            flight_number = self.data.get('flight_number', 'N/A') if isinstance(self.data, dict) else 'N/A'
            flight_date = self.data.get('flight_date', 'N/A') if isinstance(self.data, dict) else 'N/A'
            departure_time = self.data.get('departure_time', 'N/A') if isinstance(self.data, dict) else 'N/A'
            arrival_time = self.data.get('arrival_time', 'N/A') if isinstance(self.data, dict) else 'N/A'
            from_airport = self.data.get('from_airport', 'N/A') if isinstance(self.data, dict) else 'N/A'
            to_airport = self.data.get('to_airport', 'N/A') if isinstance(self.data, dict) else 'N/A'
            seat = self.data.get('seat', 'N/A') if isinstance(self.data, dict) else 'N/A'
            travel_class = self.data.get('travel_class', 'N/A') if isinstance(self.data, dict) else 'N/A'
            
            ticket_data = [
                ["Ticket Number:", self.document.document_number],
                ["Booking Reference:", booking_ref],
                ["Passenger:", passenger_name],
                ["Flight:", flight_number],
                ["Date:", flight_date],
                ["Departure:", departure_time],
                ["Arrival:", arrival_time],
                ["From:", from_airport],
                ["To:", to_airport],
                ["Seat:", seat],
                ["Class:", travel_class],
            ]
            
            ticket_table = Table(ticket_data, colWidths=[1.5*inch, 3.5*inch])
            ticket_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(ticket_table)
            
            # Boarding Pass QR
            if QRCODE_AVAILABLE:
                try:
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr_data = f"https://flynjet.com/boarding/{self.document.access_token}"
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    
                    qr_buffer = io.BytesIO()
                    qr_img.save(qr_buffer, format='PNG')
                    qr_buffer.seek(0)
                    
                    qr_platypus = Image(qr_buffer, width=1.5*inch, height=1.5*inch)
                    story.append(Spacer(1, 0.2*inch))
                    story.append(qr_platypus)
                except Exception as e:
                    logger.error(f"Error generating QR code: {e}")
            
            doc.build(story)
            buffer.seek(0)
            
            return ContentFile(buffer.getvalue(), f"ticket_{self.document.document_number}.pdf")
            
        except Exception as e:
            logger.error(f"Error generating ticket PDF: {e}")
            return self.generate_text()
    
    def generate_contract_pdf(self):
        """Generate contract PDF"""
        if not REPORTLAB_AVAILABLE:
            return self.generate_text()
        
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            
            styles = getSampleStyleSheet()
            
            # Header
            story.append(Paragraph("FLYNJET CHARTER AGREEMENT", styles['Title']))
            story.append(Spacer(1, 0.2*inch))
            
            # Contract Number
            story.append(Paragraph(f"Contract No: {self.document.document_number}", styles['Normal']))
            story.append(Paragraph(f"Date: {timezone.now().strftime('%B %d, %Y')}", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            
            # Parties
            story.append(Paragraph("THIS AGREEMENT is made between:", styles['Heading2']))
            
            customer_name = self.data.get('customer_name', '') if isinstance(self.data, dict) else ''
            customer_address = self.data.get('customer_address', '') if isinstance(self.data, dict) else ''
            
            contract_data = [
                ["FlynJet Air and Logistics.", "and", customer_name],
                ["Jomo Kenyatta International Airport. Airport Nort Road, Embakasi", "", customer_address],
                ["Nairobi, Kenya P.O. Box 19087-00501", "", ""],
            ]
            contract_table = Table(contract_data, colWidths=[2.5*inch, 0.5*inch, 2.5*inch])
            contract_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(contract_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Flight Details
            story.append(Paragraph("1. FLIGHT DETAILS", styles['Heading3']))
            
            aircraft = self.data.get('aircraft', 'N/A') if isinstance(self.data, dict) else 'N/A'
            departure_airport = self.data.get('departure_airport', 'N/A') if isinstance(self.data, dict) else 'N/A'
            arrival_airport = self.data.get('arrival_airport', 'N/A') if isinstance(self.data, dict) else 'N/A'
            flight_date = self.data.get('flight_date', 'N/A') if isinstance(self.data, dict) else 'N/A'
            departure_time = self.data.get('departure_time', 'N/A') if isinstance(self.data, dict) else 'N/A'
            arrival_time = self.data.get('arrival_time', 'N/A') if isinstance(self.data, dict) else 'N/A'
            passenger_count = self.data.get('passenger_count', 1) if isinstance(self.data, dict) else 1
            
            flight_data = [
                ["Aircraft:", aircraft],
                ["Departure:", departure_airport],
                ["Arrival:", arrival_airport],
                ["Date:", flight_date],
                ["Departure Time:", departure_time],
                ["Arrival Time:", arrival_time],
                ["Passengers:", str(passenger_count)],
            ]
            flight_table = Table(flight_data, colWidths=[1.5*inch, 4*inch])
            flight_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ]))
            story.append(flight_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Terms and Conditions
            story.append(Paragraph("2. TERMS AND CONDITIONS", styles['Heading3']))
            terms_text = """
            This Charter Agreement is subject to the following terms and conditions:
            
            2.1 The Charterer agrees to pay the total charter price as specified.
            2.2 Cancellation policy applies as per FlynJet's terms.
            2.3 The aircraft will be operated in accordance with all applicable regulations.
            2.4 FlynJet reserves the right to substitute aircraft with similar or larger equipment.
            2.5 The Charterer is responsible for all passenger compliance with safety regulations.
            """
            story.append(Paragraph(terms_text, styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            
            # Pricing
            story.append(Paragraph("3. PRICING", styles['Heading3']))
            
            base_price = self.data.get('base_price', 0) if isinstance(self.data, dict) else 0
            taxes = self.data.get('taxes', 0) if isinstance(self.data, dict) else 0
            total = self.data.get('total', 0) if isinstance(self.data, dict) else 0
            
            price_data = [
                ["Base Price:", f"${base_price:.2f}"],
                ["Taxes & Fees:", f"${taxes:.2f}"],
                ["Total Amount:", f"${total:.2f}"],
            ]
            price_table = Table(price_data, colWidths=[2*inch, 2*inch])
            price_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
            ]))
            story.append(price_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Signatures
            story.append(Paragraph("4. SIGNATURES", styles['Heading3']))
            signature_data = [
                ["For FlynJet Air and Logistics.", "", "For Charterer"],
                ["", "", ""],
                ["Name: ________________", "", "Name: ________________"],
                ["Date: ________________", "", "Date: ________________"],
                ["Signature: ________________", "", "Signature: ________________"],
            ]
            signature_table = Table(signature_data, colWidths=[2.5*inch, 0.5*inch, 2.5*inch])
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'LEFT'),
                ('SPAN', (0, 0), (0, 0)),
                ('SPAN', (2, 0), (2, 0)),
            ]))
            story.append(signature_table)
            
            doc.build(story)
            buffer.seek(0)
            
            return ContentFile(buffer.getvalue(), f"contract_{self.document.document_number}.pdf")
            
        except Exception as e:
            logger.error(f"Error generating contract PDF: {e}")
            return self.generate_text()