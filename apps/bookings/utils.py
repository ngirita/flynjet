# apps/bookings/utils.py - ENHANCED WITH AIRPORT NAMES

import hashlib
import qrcode
import traceback
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from .models import Invoice, Booking
from apps.airports.models import Airport  # Add this import
import logging
import inspect

logger = logging.getLogger(__name__)

def generate_invoice_pdf(invoice):
    """Generate PDF invoice with airport names."""
    
    # ========== DEBUGGING SECTION ==========
    print("\n" + "=" * 80)
    print("DEBUG: generate_invoice_pdf called")
    print("=" * 80)
    
    # Print the type of invoice
    print(f"Type of invoice: {type(invoice)}")
    print(f"Is invoice a dict? {isinstance(invoice, dict)}")
    print(f"Is invoice a model? {hasattr(invoice, '_meta')}")
    
    # If it's a dictionary, print its keys
    if isinstance(invoice, dict):
        print("Invoice is a DICTIONARY with keys:")
        for key in invoice.keys():
            print(f"  - {key}: {type(invoice[key])}")
    
    # Print all attributes if it's an object
    if hasattr(invoice, '__dict__'):
        print("Invoice attributes:")
        for attr in dir(invoice):
            if not attr.startswith('_'):
                print(f"  - {attr}: {type(getattr(invoice, attr, 'N/A'))}")
    
    # Check for the 'has_changed' attribute specifically
    print(f"Has 'has_changed' attribute? {hasattr(invoice, 'has_changed')}")
    if hasattr(invoice, 'has_changed'):
        print(f"has_changed value: {invoice.has_changed}")
    
    print("=" * 80)
    print("Attempting to generate PDF...")
    print("=" * 80)
    # ========== END DEBUGGING SECTION ==========
    
    try:
        # Check if invoice is a dictionary or model instance
        if isinstance(invoice, dict):
            logger.error(f"Invoice is a dictionary, not a model instance")
            print(f"ERROR: Invoice is a dictionary! Converting to model instance...")
            
            # Try to convert dictionary to model instance if it has an id
            if 'id' in invoice and invoice['id']:
                try:
                    from .models import Invoice
                    invoice = Invoice.objects.get(id=invoice['id'])
                    print(f"Successfully retrieved Invoice model with ID: {invoice.id}")
                except Exception as e:
                    print(f"Failed to retrieve Invoice: {e}")
                    return ContentFile(f"Error: Invalid invoice data".encode(), f"invoice_error.txt")
            else:
                return ContentFile(f"Error: Invoice dictionary has no ID".encode(), f"invoice_error.txt")
        
        # Verify it's a Django model instance
        if not hasattr(invoice, '_meta'):
            logger.error(f"Invoice is not a Django model instance: {type(invoice)}")
            print(f"ERROR: Invoice is not a Django model instance: {type(invoice)}")
            return ContentFile(f"Error: Invalid invoice object".encode(), f"invoice_error.txt")
        
        # Check if invoice has required attributes
        if not hasattr(invoice, 'invoice_number'):
            logger.error(f"Invoice missing invoice_number attribute")
            return ContentFile(f"Error: Invalid invoice object - missing invoice_number".encode(), f"invoice_error.txt")
        
        # Get airport names for the invoice
        departure_airport_info = None
        arrival_airport_info = None
        
        if hasattr(invoice, 'booking') and invoice.booking:
            booking = invoice.booking
            
            # Get departure airport info
            if booking.departure_airport:
                try:
                    dep_airport = Airport.objects.get(iata_code=booking.departure_airport)
                    departure_airport_info = {
                        'iata': dep_airport.iata_code,
                        'name': dep_airport.name,
                        'city': dep_airport.city,
                        'country': dep_airport.country
                    }
                except Airport.DoesNotExist:
                    departure_airport_info = {'iata': booking.departure_airport, 'name': None}
            
            # Get arrival airport info
            if booking.arrival_airport:
                try:
                    arr_airport = Airport.objects.get(iata_code=booking.arrival_airport)
                    arrival_airport_info = {
                        'iata': arr_airport.iata_code,
                        'name': arr_airport.name,
                        'city': arr_airport.city,
                        'country': arr_airport.country
                    }
                except Airport.DoesNotExist:
                    arrival_airport_info = {'iata': booking.arrival_airport, 'name': None}
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Header
        p.setFont("Helvetica-Bold", 20)
        p.drawString(50, height - 50, "FlynJet")
        
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, "INVOICE")
        
        # Invoice details
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, height - 100, f"Invoice Number: {getattr(invoice, 'invoice_number', 'N/A')}")
        p.drawString(50, height - 115, f"Date: {getattr(invoice, 'invoice_date', timezone.now().date())}")
        p.drawString(50, height - 130, f"Due Date: {getattr(invoice, 'due_date', timezone.now().date())}")
        
        # Flight Information (if available)
        if departure_airport_info or arrival_airport_info:
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, height - 155, "Flight Information:")
            p.setFont("Helvetica", 10)
            y = height - 170
            
            if departure_airport_info:
                dep_text = f"From: {departure_airport_info['city']} ({departure_airport_info['iata']})"
                if departure_airport_info['name']:
                    dep_text += f" - {departure_airport_info['name']}"
                p.drawString(50, y, dep_text)
                y -= 15
            
            if arrival_airport_info:
                arr_text = f"To: {arrival_airport_info['city']} ({arrival_airport_info['iata']})"
                if arrival_airport_info['name']:
                    arr_text += f" - {arrival_airport_info['name']}"
                p.drawString(50, y, arr_text)
                y -= 15
            
            # Add flight dates if available
            if hasattr(invoice, 'booking') and invoice.booking:
                booking = invoice.booking
                if booking.departure_datetime:
                    p.drawString(50, y, f"Departure: {booking.departure_datetime.strftime('%B %d, %Y at %I:%M %p')}")
                    y -= 15
                if booking.arrival_datetime:
                    p.drawString(50, y, f"Arrival: {booking.arrival_datetime.strftime('%B %d, %Y at %I:%M %p')}")
                    y -= 15
            
            y -= 15  # Extra spacing before billing address
        else:
            y = height - 175
        
        # Billing address
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Bill To:")
        p.setFont("Helvetica", 10)
        y -= 15
        
        billing_company = getattr(invoice, 'billing_company_name', '')
        if billing_company:
            p.drawString(50, y, str(billing_company))
            y -= 15
        
        billing_address = getattr(invoice, 'billing_address_line1', 'Not provided')
        p.drawString(50, y, str(billing_address))
        y -= 15
        
        billing_address2 = getattr(invoice, 'billing_address_line2', '')
        if billing_address2:
            p.drawString(50, y, str(billing_address2))
            y -= 15
        
        billing_city = getattr(invoice, 'billing_city', 'Nairobi')
        billing_state = getattr(invoice, 'billing_state', 'Nairobi')
        billing_postal = getattr(invoice, 'billing_postal_code', '00100')
        p.drawString(50, y, f"{billing_city}, {billing_state} {billing_postal}")
        y -= 15
        
        billing_country = getattr(invoice, 'billing_country', 'Kenya')
        p.drawString(50, y, billing_country)
        y -= 25  # Spacing before table
        
        # Items table
        data = [['Description', 'Quantity', 'Unit Price', 'Total']]
        
        # Safely get items
        print("\n" + "=" * 80)
        print("DEBUG: Attempting to get invoice items...")
        print(f"Invoice type: {type(invoice)}")
        print(f"Has 'items' attribute? {hasattr(invoice, 'items')}")
        
        try:
            if hasattr(invoice, 'items'):
                print("Invoice has 'items' attribute")
                items_manager = invoice.items
                print(f"items manager type: {type(items_manager)}")
                print(f"Has 'all' method? {hasattr(items_manager, 'all')}")
                
                items = items_manager.all() if hasattr(items_manager, 'all') else []
                print(f"Retrieved {len(items)} items")
            else:
                print("Invoice has NO 'items' attribute")
                items = []
        except Exception as e:
            print(f"ERROR getting items: {e}")
            logger.error(f"Error getting invoice items: {e}", exc_info=True)
            items = []
        
        for idx, item in enumerate(items):
            print(f"Processing item {idx}: {type(item)}")
            if item:
                try:
                    description = str(item.description)[:50] if hasattr(item, 'description') else 'N/A'
                    quantity = str(item.quantity) if hasattr(item, 'quantity') else '1'
                    unit_price = float(item.unit_price_usd) if hasattr(item, 'unit_price_usd') else 0
                    line_total = float(item.line_total_usd) if hasattr(item, 'line_total_usd') else 0
                    
                    data.append([
                        description,
                        quantity,
                        f"${unit_price:.2f}",
                        f"${line_total:.2f}"
                    ])
                except Exception as e:
                    print(f"Error processing item {idx}: {e}")
                    logger.error(f"Error processing item: {e}", exc_info=True)
                    continue
        
        print(f"Data table has {len(data)} rows")
        print("=" * 80)
        
        # Totals
        subtotal = float(getattr(invoice, 'subtotal_usd', 0))
        tax_amount = float(getattr(invoice, 'tax_amount_usd', 0))
        discount = float(getattr(invoice, 'discount_amount_usd', 0))
        total = float(getattr(invoice, 'total_usd', 0))
        
        data.append(['', '', 'Subtotal:', f"${subtotal:.2f}"])
        data.append(['', '', 'Tax:', f"${tax_amount:.2f}"])
        if discount > 0:
            data.append(['', '', 'Discount:', f"${discount:.2f}"])
        data.append(['', '', 'Total:', f"${total:.2f}"])
        
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),  # Right-align price columns
        ]))
        
        table.wrapOn(p, width - 100, y - 50)
        table.drawOn(p, 50, y - 300)
        
        # Generate QR Code
        verification_hash = getattr(invoice, 'verification_hash', '')
        if verification_hash:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(str(verification_hash))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR to buffer
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            
            # Draw QR on PDF
            p.drawImage(qr_buffer, width - 150, height - 150, width=100, height=100)
        
        # Add footer
        p.setFont("Helvetica", 8)
        p.drawString(50, 50, "Thank you for choosing FlynJet!")
        p.drawString(50, 35, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        p.save()
        buffer.seek(0)
        
        print("PDF generated successfully!")
        return ContentFile(buffer.getvalue(), f"invoice_{getattr(invoice, 'invoice_number', 'unknown')}.pdf")
        
    except Exception as e:
        print(f"CRITICAL ERROR generating PDF: {e}")
        print(traceback.format_exc())
        logger.error(f"Error generating PDF for invoice: {e}", exc_info=True)
        return ContentFile(f"Error generating PDF: {str(e)}".encode(), f"invoice_error.txt")