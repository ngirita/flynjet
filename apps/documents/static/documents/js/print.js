// Document Printing Utilities

class DocumentPrinter {
    constructor(options = {}) {
        this.documentId = options.documentId;
        this.printFrame = null;
        this.printStyles = options.printStyles || [];
    }
    
    print() {
        this.createPrintFrame();
        this.loadDocument();
    }
    
    createPrintFrame() {
        this.printFrame = document.createElement('iframe');
        this.printFrame.style.position = 'absolute';
        this.printFrame.style.width = '0';
        this.printFrame.style.height = '0';
        this.printFrame.style.border = 'none';
        document.body.appendChild(this.printFrame);
    }
    
    loadDocument() {
        fetch(`/api/v1/documents/${this.documentId}/`)
            .then(response => response.json())
            .then(data => {
                this.renderDocument(data);
            })
            .catch(error => {
                console.error('Error loading document:', error);
            });
    }
    
    renderDocument(data) {
        const doc = this.printFrame.contentWindow.document;
        
        // Write document content
        doc.write('<!DOCTYPE html>');
        doc.write('<html>');
        doc.write('<head>');
        doc.write('<meta charset="utf-8">');
        doc.write('<title>' + data.title + '</title>');
        
        // Add styles
        this.addStyles(doc);
        
        doc.write('</head>');
        doc.write('<body>');
        
        // Document content based on type
        if (data.document_type === 'invoice') {
            this.renderInvoice(doc, data);
        } else if (data.document_type === 'ticket') {
            this.renderTicket(doc, data);
        } else if (data.document_type === 'contract') {
            this.renderContract(doc, data);
        } else {
            doc.write('<div class="document-content">');
            doc.write('<pre>' + JSON.stringify(data.content_data, null, 2) + '</pre>');
            doc.write('</div>');
        }
        
        doc.write('</body>');
        doc.write('</html>');
        
        doc.close();
        
        // Wait for resources to load then print
        setTimeout(() => {
            this.printFrame.contentWindow.print();
        }, 500);
    }
    
    addStyles(doc) {
        // Add default print styles
        doc.write('<link rel="stylesheet" href="/static/documents/css/print.css">');
        
        // Add custom styles
        this.printStyles.forEach(styleUrl => {
            doc.write('<link rel="stylesheet" href="' + styleUrl + '">');
        });
        
        // Add inline styles for better print formatting
        doc.write('<style>');
        doc.write(`
            body {
                font-family: Arial, sans-serif;
                margin: 1cm;
                line-height: 1.5;
            }
            .document-header {
                text-align: center;
                margin-bottom: 20px;
            }
            .document-footer {
                text-align: center;
                margin-top: 50px;
                font-size: 10px;
                color: #666;
            }
            .watermark {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%) rotate(-45deg);
                font-size: 60px;
                color: rgba(0,0,0,0.1);
                z-index: -1;
            }
        `);
        doc.write('</style>');
    }
    
    renderInvoice(doc, data) {
        const content = data.content_data;
        
        doc.write('<div class="document">');
        doc.write('<div class="document-header">');
        doc.write('<h1>INVOICE</h1>');
        doc.write('<p>' + data.document_number + '</p>');
        doc.write('</div>');
        
        doc.write('<div class="company-details">');
        doc.write('<h3>FlynJet Inc.</h3>');
        doc.write('<p>123 Aviation Way<br>Miami, FL 33101</p>');
        doc.write('</div>');
        
        doc.write('<div class="invoice-details">');
        doc.write('<p><strong>Date:</strong> ' + new Date(data.created_at).toLocaleDateString() + '</p>');
        doc.write('<p><strong>Due Date:</strong> ' + new Date(content.due_date).toLocaleDateString() + '</p>');
        doc.write('</div>');
        
        doc.write('<div class="billing-info">');
        doc.write('<h3>Bill To:</h3>');
        doc.write('<p><strong>' + content.customer_name + '</strong></p>');
        doc.write('<p>' + content.customer_email + '</p>');
        doc.write('</div>');
        
        doc.write('<table class="items-table">');
        doc.write('<thead><tr><th>Description</th><th>Quantity</th><th>Price</th><th>Total</th></tr></thead>');
        doc.write('<tbody>');
        
        if (content.items) {
            content.items.forEach(item => {
                doc.write('<tr>');
                doc.write('<td>' + item.description + '</td>');
                doc.write('<td>' + item.quantity + '</td>');
                doc.write('<td>$' + item.unit_price.toFixed(2) + '</td>');
                doc.write('<td>$' + item.total.toFixed(2) + '</td>');
                doc.write('</tr>');
            });
        }
        
        doc.write('</tbody>');
        doc.write('</table>');
        
        doc.write('<div class="totals">');
        doc.write('<p><strong>Subtotal:</strong> $' + content.subtotal.toFixed(2) + '</p>');
        doc.write('<p><strong>Tax:</strong> $' + content.tax.toFixed(2) + '</p>');
        doc.write('<h3>Total: $' + content.total.toFixed(2) + '</h3>');
        doc.write('</div>');
        
        doc.write('<div class="document-footer">');
        doc.write('<p>Thank you for choosing FlynJet!</p>');
        doc.write('</div>');
        
        doc.write('</div>');
    }
    
    renderTicket(doc, data) {
        const content = data.content_data;
        
        doc.write('<div class="boarding-pass">');
        doc.write('<div class="header">');
        doc.write('<h1>FlynJet</h1>');
        doc.write('<h2>BOARDING PASS</h2>');
        doc.write('</div>');
        
        doc.write('<div class="passenger-info">');
        doc.write('<p><strong>Passenger:</strong> ' + content.passenger_name + '</p>');
        doc.write('<p><strong>Flight:</strong> ' + content.flight_number + '</p>');
        doc.write('</div>');
        
        doc.write('<div class="flight-route">');
        doc.write('<div class="departure">');
        doc.write('<div class="airport-code">' + content.from_airport + '</div>');
        doc.write('<div>' + new Date(content.departure_time).toLocaleTimeString() + '</div>');
        doc.write('</div>');
        doc.write('<div class="arrow">→</div>');
        doc.write('<div class="arrival">');
        doc.write('<div class="airport-code">' + content.to_airport + '</div>');
        doc.write('<div>' + new Date(content.arrival_time).toLocaleTimeString() + '</div>');
        doc.write('</div>');
        doc.write('</div>');
        
        doc.write('<div class="details">');
        doc.write('<p><strong>Seat:</strong> ' + (content.seat || 'TBA') + '</p>');
        doc.write('<p><strong>Gate:</strong> ' + (content.gate || 'TBA') + '</p>');
        doc.write('<p><strong>Boarding:</strong> ' + (content.boarding_time || '30 min before') + '</p>');
        doc.write('</div>');
        
        doc.write('<div class="barcode">');
        doc.write('*' + data.document_number + '*');
        doc.write('</div>');
        
        doc.write('</div>');
    }
    
    renderContract(doc, data) {
        const content = data.content_data;
        
        doc.write('<div class="contract">');
        doc.write('<h1>AIRCRAFT CHARTER AGREEMENT</h1>');
        doc.write('<p class="contract-number">Contract No: ' + data.document_number + '</p>');
        
        doc.write('<div class="parties">');
        doc.write('<h3>THIS AGREEMENT is made between:</h3>');
        doc.write('<p><strong>FlynJet Inc.</strong> (hereinafter "the Operator")</p>');
        doc.write('<p>AND</p>');
        doc.write('<p><strong>' + content.customer_name + '</strong> (hereinafter "the Charterer")</p>');
        doc.write('</div>');
        
        doc.write('<div class="recitals">');
        doc.write('<p>WHEREAS the Operator is engaged in the business of chartering private aircraft;</p>');
        doc.write('<p>WHEREAS the Charterer desires to charter an aircraft from the Operator;</p>');
        doc.write('<p>NOW THEREFORE the parties agree as follows:</p>');
        doc.write('</div>');
        
        // Contract clauses
        const clauses = [
            {
                number: 1,
                title: "FLIGHT DETAILS",
                content: "The Operator agrees to provide and the Charterer agrees to charter the aircraft for the flight from " + 
                        content.from_airport + " to " + content.to_airport + " on " + 
                        new Date(content.flight_date).toLocaleDateString() + "."
            },
            {
                number: 2,
                title: "CHARGES",
                content: "The total charter price is $" + content.total + " USD, payable prior to departure."
            },
            {
                number: 3,
                title: "CANCELLATION",
                content: "Cancellations made 48 hours or more before departure receive a full refund. Cancellations within 48 hours are subject to a 50% cancellation fee."
            }
        ];
        
        clauses.forEach(clause => {
            doc.write('<div class="clause">');
            doc.write('<h4>' + clause.number + '. ' + clause.title + '</h4>');
            doc.write('<p>' + clause.content + '</p>');
            doc.write('</div>');
        });
        
        doc.write('<div class="signature-area">');
        doc.write('<div class="signature-box">');
        doc.write('<p>For FlynJet Inc.</p>');
        doc.write('<div class="signature-line"></div>');
        doc.write('<p>Authorized Signature</p>');
        doc.write('</div>');
        doc.write('<div class="signature-box">');
        doc.write('<p>For Charterer</p>');
        doc.write('<div class="signature-line"></div>');
        doc.write('<p>Authorized Signature</p>');
        doc.write('</div>');
        doc.write('</div>');
        
        doc.write('</div>');
    }
    
    destroy() {
        if (this.printFrame) {
            document.body.removeChild(this.printFrame);
            this.printFrame = null;
        }
    }
}

// Signature Capture for Document Signing
class SignatureCapture {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.drawing = false;
        this.lastX = 0;
        this.lastY = 0;
        
        this.options = {
            lineColor: options.lineColor || '#000',
            lineWidth: options.lineWidth || 2,
            ...options
        };
        
        this.init();
    }
    
    init() {
        this.setupCanvas();
        this.addEventListeners();
    }
    
    setupCanvas() {
        // Set canvas dimensions
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        // Set styles
        this.ctx.strokeStyle = this.options.lineColor;
        this.ctx.lineWidth = this.options.lineWidth;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
    }
    
    addEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseout', () => this.stopDrawing());
        
        // Touch events for mobile
        this.canvas.addEventListener('touchstart', (e) => this.startDrawing(e));
        this.canvas.addEventListener('touchmove', (e) => this.draw(e));
        this.canvas.addEventListener('touchend', () => this.stopDrawing());
    }
    
    startDrawing(e) {
        e.preventDefault();
        this.drawing = true;
        
        const pos = this.getPosition(e);
        this.lastX = pos.x;
        this.lastY = pos.y;
    }
    
    draw(e) {
        e.preventDefault();
        if (!this.drawing) return;
        
        const pos = this.getPosition(e);
        
        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(pos.x, pos.y);
        this.ctx.stroke();
        
        this.lastX = pos.x;
        this.lastY = pos.y;
    }
    
    stopDrawing() {
        this.drawing = false;
    }
    
    getPosition(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        
        let x, y;
        
        if (e.touches) {
            x = (e.touches[0].clientX - rect.left) * scaleX;
            y = (e.touches[0].clientY - rect.top) * scaleY;
        } else {
            x = (e.clientX - rect.left) * scaleX;
            y = (e.clientY - rect.top) * scaleY;
        }
        
        return { x, y };
    }
    
    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
    
    getSignatureData() {
        return this.canvas.toDataURL('image/png');
    }
    
    loadSignature(dataUrl) {
        const img = new Image();
        img.onload = () => {
            this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
        };
        img.src = dataUrl;
    }
    
    resize() {
        this.setupCanvas();
    }
}

// Document Preview
class DocumentPreview {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.documentId = options.documentId;
        this.printer = new DocumentPrinter({ documentId: this.documentId });
        
        this.init();
    }
    
    init() {
        this.loadPreview();
    }
    
    loadPreview() {
        fetch(`/api/v1/documents/${this.documentId}/`)
            .then(response => response.json())
            .then(data => {
                this.renderPreview(data);
            });
    }
    
    renderPreview(data) {
        const iframe = document.createElement('iframe');
        iframe.className = 'document-frame';
        iframe.src = data.pdf_file;
        this.container.innerHTML = '';
        this.container.appendChild(iframe);
    }
    
    print() {
        this.printer.print();
    }
    
    download() {
        window.location.href = `/api/v1/documents/${this.documentId}/download/`;
    }
}

// Export utilities
window.DocumentPrinter = DocumentPrinter;
window.SignatureCapture = SignatureCapture;
window.DocumentPreview = DocumentPreview;