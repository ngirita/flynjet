(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('=== FLEET AUTOCOMPLETE SCRIPT LOADED ===');
        
        // Create datalist element if it doesn't exist
        if ($('#airport-list').length === 0) {
            $('body').append('<datalist id="airport-list"></datalist>');
        }
        
        var $datalist = $('#airport-list');
        var typingTimer;
        var doneTypingInterval = 500;
        
        function searchAirports(query) {
            if (query.length < 2) {
                return;
            }
            
            console.log('Searching for:', query);
            
            $.ajax({
                url: '/airports/autocomplete/',
                data: { q: query },
                dataType: 'json',
                success: function(data) {
                    console.log('Results:', data.results.length);
                    $datalist.empty();
                    
                    $.each(data.results, function(index, airport) {
                        $datalist.append('<option value="' + airport.text + '" data-iata="' + airport.id + '"></option>');
                    });
                },
                error: function(xhr, status, error) {
                    console.error('AJAX error:', error);
                }
            });
        }
        
        // Handle input on both fields
        $('#id_base_airport_display, #id_current_location_display').on('input', function() {
            var $field = $(this);
            var query = $field.val();
            
            clearTimeout(typingTimer);
            
            if (query.length >= 2) {
                typingTimer = setTimeout(function() {
                    searchAirports(query);
                }, doneTypingInterval);
            } else {
                $datalist.empty();
            }
        });
        
        // Handle selection from datalist
        $('#id_base_airport_display, #id_current_location_display').on('change', function() {
            var $field = $(this);
            var selectedText = $field.val();
            
            // Find the selected option in datalist
            var $selectedOption = $datalist.find('option[value="' + selectedText + '"]');
            if ($selectedOption.length) {
                var iataCode = $selectedOption.data('iata');
                var hiddenFieldId = $field.attr('id').replace('_display', '');
                $('#' + hiddenFieldId).val(iataCode);
                console.log('Selected IATA:', iataCode);
            }
        });

        // ── NEW: Hide/show fields based on aircraft category ──────────
        function toggleCategoryFields(categorySelect) {
            var selectedText = categorySelect.find('option:selected').text().toLowerCase();
            var isCargo = selectedText.indexOf('cargo') !== -1;

            if (isCargo) {
                $('#id_passenger_capacity').closest('.form-row').hide();
                $('#id_cargo_capacity_kg').closest('.form-row').show();
                $('#id_cargo_capacity_kg').prop('required', true);
                $('#id_passenger_capacity').val('0');
                // Show dimensions for cargo
                $('#id_length_m').closest('.form-row').show();
                $('#id_wingspan_m').closest('.form-row').show();
                $('#id_height_m').closest('.form-row').show();
            } else {
                $('#id_passenger_capacity').closest('.form-row').show();
                $('#id_cargo_capacity_kg').closest('.form-row').hide();
                $('#id_cargo_capacity_kg').prop('required', false);
                $('#id_cargo_capacity_kg').val('');
                // Hide dimensions for non-cargo
                $('#id_length_m').closest('.form-row').hide();
                $('#id_wingspan_m').closest('.form-row').hide();
                $('#id_height_m').closest('.form-row').hide();
            }
        }

        var $categorySelect = $('#id_category');

        // Run on page load (handles editing existing aircraft)
        if ($categorySelect.length) {
            toggleCategoryFields($categorySelect);
        }

        // Run on change (handles selecting category when adding new aircraft)
        $categorySelect.on('change', function() {
            toggleCategoryFields($(this));
        });
        // ── END NEW ───────────────────────────────────────────────────

    });
    
})(jQuery);