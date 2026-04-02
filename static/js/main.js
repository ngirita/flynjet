// Main JavaScript file for FlynJet

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Add animation on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate__animated', 'animate__fadeInUp');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .aircraft-card').forEach(el => {
        observer.observe(el);
    });
});

// Password strength indicator
function checkPasswordStrength(password) {
    let strength = 0;
    
    if (password.length >= 12) strength++;
    if (password.match(/[a-z]+/)) strength++;
    if (password.match(/[A-Z]+/)) strength++;
    if (password.match(/[0-9]+/)) strength++;
    if (password.match(/[$@#&!]+/)) strength++;
    
    return strength;
}

// Update password strength on input
document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.querySelector('#id_password1');
    const strengthIndicator = document.querySelector('#password-strength');
    
    if (passwordInput && strengthIndicator) {
        passwordInput.addEventListener('input', function() {
            const strength = checkPasswordStrength(this.value);
            const strengthText = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong'];
            const strengthClass = ['danger', 'warning', 'info', 'primary', 'success'];
            
            strengthIndicator.innerHTML = `
                <div class="progress mt-2">
                    <div class="progress-bar bg-${strengthClass[strength-1]}" 
                         role="progressbar" 
                         style="width: ${strength * 20}%">
                        ${strengthText[strength-1]}
                    </div>
                </div>
            `;
        });
    }
});

// Live flight tracking simulation
class FlightTracker {
    constructor(flightNumber, elementId) {
        this.flightNumber = flightNumber;
        this.element = document.getElementById(elementId);
        this.updateInterval = null;
    }

    startTracking() {
        this.updateInterval = setInterval(() => this.updatePosition(), 5000);
    }

    updatePosition() {
        fetch(`/api/tracking/${this.flightNumber}/`)
            .then(response => response.json())
            .then(data => {
                this.updateMap(data.position);
                this.updateInfo(data);
            })
            .catch(error => console.error('Tracking error:', error));
    }

    updateMap(position) {
        // Update map with new position
    }

    updateInfo(data) {
        if (this.element) {
            this.element.innerHTML = `
                <div class="flight-info">
                    <p>Altitude: ${data.altitude} ft</p>
                    <p>Speed: ${data.speed} knots</p>
                    <p>ETA: ${data.eta}</p>
                </div>
            `;
        }
    }

    stopTracking() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }
}

// Booking form validation
function validateBookingForm(form) {
    const errors = [];
    const departure = form.querySelector('[name="departure"]').value;
    const arrival = form.querySelector('[name="arrival"]').value;
    const date = new Date(form.querySelector('[name="date"]').value);

    if (departure === arrival) {
        errors.push('Departure and arrival airports must be different');
    }

    if (date < new Date()) {
        errors.push('Departure date must be in the future');
    }

    if (errors.length > 0) {
        showErrors(errors);
        return false;
    }

    return true;
}

function showErrors(errors) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.innerHTML = errors.map(error => `<p class="mb-0">${error}</p>`).join('');
    
    const form = document.querySelector('form');
    form.insertBefore(errorDiv, form.firstChild);
    
    setTimeout(() => errorDiv.remove(), 5000);
}

// Payment form handling
class PaymentHandler {
    constructor(stripePublicKey) {
        this.stripe = Stripe(stripePublicKey);
        this.elements = this.stripe.elements();
        this.card = null;
    }

    initCardElement(elementId) {
        this.card = this.elements.create('card', {
            style: {
                base: {
                    fontSize: '16px',
                    color: '#32325d',
                    fontFamily: '"Helvetica Neue", Helvetica, sans-serif',
                }
            }
        });
        this.card.mount(elementId);
    }

    async processPayment(formData) {
        const { paymentMethod, error } = await this.stripe.createPaymentMethod({
            type: 'card',
            card: this.card,
            billing_details: {
                name: formData.name,
                email: formData.email,
            },
        });

        if (error) {
            throw new Error(error.message);
        }

        return paymentMethod;
    }
}

// Chat widget
class ChatWidget {
    constructor() {
        this.socket = null;
        this.isOpen = false;
    }

    initialize() {
        this.createWidget();
        this.setupEventListeners();
    }

    createWidget() {
        const widget = document.createElement('div');
        widget.id = 'chat-widget';
        widget.innerHTML = `
            <div class="chat-button">
                <i class="fas fa-comment"></i>
            </div>
            <div class="chat-window hidden">
                <div class="chat-header">
                    <h5>FlynJet Support</h5>
                    <button class="close-chat">&times;</button>
                </div>
                <div class="chat-messages"></div>
                <div class="chat-input">
                    <input type="text" placeholder="Type your message...">
                    <button class="send-message">Send</button>
                </div>
            </div>
        `;
        document.body.appendChild(widget);
    }

    setupEventListeners() {
        const chatButton = document.querySelector('.chat-button');
        const closeButton = document.querySelector('.close-chat');
        const sendButton = document.querySelector('.send-message');
        const input = document.querySelector('.chat-input input');

        chatButton.addEventListener('click', () => this.toggleChat());
        closeButton.addEventListener('click', () => this.toggleChat());
        sendButton.addEventListener('click', () => this.sendMessage());
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }

    toggleChat() {
        const window = document.querySelector('.chat-window');
        this.isOpen = !this.isOpen;
        window.classList.toggle('hidden');
        
        if (this.isOpen && !this.socket) {
            this.connectWebSocket();
        }
    }

    connectWebSocket() {
        this.socket = new WebSocket('ws://localhost:8000/ws/chat/');
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.displayMessage(data.message, 'received');
        };
    }

    sendMessage() {
        const input = document.querySelector('.chat-input input');
        const message = input.value.trim();
        
        if (message) {
            this.displayMessage(message, 'sent');
            this.socket.send(JSON.stringify({ message: message }));
            input.value = '';
        }
    }

    displayMessage(message, type) {
        const messagesDiv = document.querySelector('.chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.innerHTML = `
            <div class="message-content">${message}</div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize chat widget
    if (document.querySelector('#enable-chat')) {
        const chat = new ChatWidget();
        chat.initialize();
    }

    // Initialize payment handler if on payment page
    if (document.querySelector('#payment-form')) {
        const paymentHandler = new PaymentHandler(stripePublicKey);
        paymentHandler.initCardElement('#card-element');
    }
});