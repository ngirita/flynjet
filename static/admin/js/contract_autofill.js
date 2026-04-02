// static/admin/js/contract_autofill.js
(function($) {
    'use strict';
    
    console.log("Contract autofill script loaded");
    
    $(document).ready(function() {
        console.log("Document ready, looking for enquiry dropdown");
        
        // Function to find and setup the dropdown (runs every 500ms until found)
        function findAndSetup() {
            var enquirySelect = $('#id_enquiry');
            
            if (enquirySelect.length === 0) {
                console.log("Enquiry dropdown not found yet, retrying...");
                setTimeout(findAndSetup, 500);
                return;
            }
            
            console.log("Found enquiry dropdown!");
            console.log("Options count:", enquirySelect.find('option').length);
            
            // Create message container
            var messageContainer = $('<div id="contract-autofill-message" style="margin: 10px 0; padding: 10px; border-radius: 4px; display: none;"></div>');
            enquirySelect.parent().after(messageContainer);
            
            function showMessage(msg, isSuccess) {
                if (isSuccess) {
                    messageContainer.css({
                        'background-color': '#d4edda',
                        'color': '#155724',
                        'border': '1px solid #c3e6cb'
                    });
                } else {
                    messageContainer.css({
                        'background-color': '#f8d7da',
                        'color': '#721c24',
                        'border': '1px solid #f5c6cb'
                    });
                }
                messageContainer.html('<i class="fas fa-' + (isSuccess ? 'check-circle' : 'exclamation-circle') + '"></i> ' + msg);
                messageContainer.fadeIn();
                setTimeout(function() { messageContainer.fadeOut(); }, 5000);
            }
            
            function autoFill() {
                var enquiryId = enquirySelect.val();
                console.log("Selected enquiry ID:", enquiryId);
                
                if (!enquiryId) {
                    console.log("No enquiry selected");
                    return;
                }
                
                // Show loading
                $('#id_client_name, #id_client_email, #id_client_phone').css('background-color', '#fff3cd');
                
                console.log("Fetching from:", '/admin/api/enquiry/' + enquiryId + '/');
                
                $.ajax({
                    url: '/admin/api/enquiry/' + enquiryId + '/',
                    method: 'GET',
                    dataType: 'json',
                    success: function(data) {
                        console.log("Data received:", data);
                        
                        // Fill all fields
                        if (data.client_name) $('#id_client_name').val(data.client_name);
                        if (data.client_email) $('#id_client_email').val(data.client_email);
                        if (data.client_phone) $('#id_client_phone').val(data.client_phone);
                        if (data.aircraft_id) $('#id_aircraft').val(data.aircraft_id);
                        if (data.passenger_count) $('#id_passenger_count').val(data.passenger_count);
                        if (data.luggage_weight_kg) $('#id_luggage_weight_kg').val(data.luggage_weight_kg);
                        if (data.departure_airport) $('#id_departure_airport').val(data.departure_airport);
                        if (data.arrival_airport) $('#id_arrival_airport').val(data.arrival_airport);
                        if (data.valid_until) $('#id_valid_until').val(data.valid_until);
                        if (data.departure_datetime) $('#id_departure_datetime').val(data.departure_datetime);
                        if (data.arrival_datetime) $('#id_arrival_datetime').val(data.arrival_datetime);
                        
                        // Reset loading style
                        $('#id_client_name, #id_client_email, #id_client_phone').css('background-color', '');
                        
                        showMessage('Auto-filled from enquiry ' + data.enquiry_number, true);
                    },
                    error: function(xhr) {
                        console.error('AJAX error:', xhr.status, xhr.responseText);
                        $('#id_client_name, #id_client_email, #id_client_phone').css('background-color', '');
                        showMessage('Error loading enquiry: ' + (xhr.responseJSON?.error || 'Unknown error'), false);
                    }
                });
            }
            
            // Listen for changes
            enquirySelect.on('change', autoFill);
            
            // If already has a value, auto-fill
            if (enquirySelect.val()) {
                autoFill();
            }
        }
        
        // Start looking for the dropdown
        findAndSetup();
    });
})(jQuery);  // Use jQuery directly, not django.jQuery