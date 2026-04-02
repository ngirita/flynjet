// static/js/airport-autocomplete.js

$(document).ready(function() {
    console.log('Airport autocomplete script loaded');
    
    function formatAirportResult(airport) {
        if (airport.loading) {
            return airport.text;
        }
        
        if (!airport.id) {
            return airport.text;
        }
        
        var city = airport.city || '';
        var name = airport.name || '';
        var iata = airport.iata || airport.id;
        var country = airport.country || '';
        
        var $container = $(
            '<div class="airport-result">' +
                '<strong>' + escapeHtml(city || name) + '</strong><br>' +
                '<small>' + escapeHtml(name) + ' (' + escapeHtml(iata) + ')' + (country ? ' - ' + escapeHtml(country) : '') + '</small>' +
            '</div>'
        );
        
        return $container;
    }
    
    function formatAirportSelection(airport) {
        if (!airport.id) {
            return airport.text;
        }
        
        var city = airport.city || '';
        var iata = airport.iata || airport.id;
        
        if (city) {
            return city + ' (' + iata + ')';
        }
        return airport.text;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        var map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
    }
    
    function initAirportAutocomplete(selectElement) {
        if (!selectElement.length) {
            console.log('Select element not found');
            return;
        }
        
        // Check if already initialized to prevent duplicate
        if (selectElement.hasClass('select2-hidden-accessible')) {
            console.log('Already initialized, skipping:', selectElement.attr('id'));
            return;
        }
        
        console.log('Initializing autocomplete for:', selectElement.attr('id'));
        
        // Get the hidden input ID
        var hiddenInputId = selectElement.attr('id').replace('_display', '_iata');
        
        // Check if this is inside a modal
        var isInModal = selectElement.closest('.modal').length > 0;
        
        // Check if this is on the home page quick booking form
        var isQuickBooking = selectElement.closest('.booking-form-section').length > 0;
        
        // Set shorter placeholder for quick booking to prevent stretching
        var placeholderText = 'Search by city, airport name, or code...';
        if (isQuickBooking) {
            placeholderText = 'Search airport...';  // Shorter text prevents stretching
        }
        
        // Common Select2 configuration
        var select2Config = {
            ajax: {
                url: '/airports/autocomplete/',
                dataType: 'json',
                delay: 300,
                data: function(params) {
                    console.log('Searching for:', params.term);
                    return {
                        q: params.term
                    };
                },
                processResults: function(data) {
                    console.log('Results received:', data.results ? data.results.length : 0);
                    var results = [];
                    if (data.results && Array.isArray(data.results)) {
                        results = data.results.map(function(item) {
                            return {
                                id: item.iata || item.id,
                                text: item.text || (item.city + ' (' + (item.iata || item.id) + ')'),
                                iata: item.iata,
                                name: item.name,
                                city: item.city,
                                country: item.country
                            };
                        });
                    }
                    return {
                        results: results
                    };
                },
                cache: true
            },
            minimumInputLength: 2,
            placeholder: placeholderText,  // Use the shorter text for quick booking
            allowClear: true,
            dropdownAutoWidth: false,
            width: '100%',
            language: {
                inputTooShort: function() {
                    return 'Enter at least 2 characters';
                },
                searching: function() {
                    return 'Searching...';
                },
                noResults: function() {
                    return 'No airports found. Try a different search.';
                }
            },
            templateResult: formatAirportResult,
            templateSelection: formatAirportSelection
        };
        
        // For quick booking form, add specific dropdown class and positioning
        if (isQuickBooking) {
            select2Config.dropdownCssClass = 'quick-booking-dropdown';
            // Don't set dropdownParent - let it use body positioning
        }
        
        // ONLY set dropdownParent if it's a modal (for enquiry forms)
        if (isInModal && !isQuickBooking) {
            select2Config.dropdownParent = selectElement.closest('.modal');
            console.log('Modal detected - setting dropdownParent');
        }
        
        selectElement.select2(select2Config);
        
        // Handle selection - update hidden field
        selectElement.on('select2:select', function(e) {
            var data = e.params.data;
            console.log('✅ Airport selected:', data);
            
            if (hiddenInputId && data && data.iata) {
                $('#' + hiddenInputId).val(data.iata);
                console.log('Hidden field', hiddenInputId, 'set to:', data.iata);
                $('#' + hiddenInputId).trigger('change');
            }
        });
        
        // Handle clearing
        selectElement.on('select2:clear', function() {
            console.log('Selection cleared for:', selectElement.attr('id'));
            if (hiddenInputId) {
                $('#' + hiddenInputId).val('');
                $('#' + hiddenInputId).trigger('change');
            }
        });
        
        // Also handle change event
        selectElement.on('change', function() {
            var selectedValue = selectElement.val();
            console.log('Change event - Selected value:', selectedValue);
            if (selectedValue && hiddenInputId) {
                $('#' + hiddenInputId).val(selectedValue);
            }
        });
    }
    
    // Initialize all airport autocomplete fields
    $('.airport-autocomplete').each(function() {
        initAirportAutocomplete($(this));
    });
    
    // Function to reinitialize Select2 for modal (enquiry forms)
    window.reinitModalAutocomplete = function() {
        $('.airport-autocomplete').each(function() {
            var $element = $(this);
            
            // Only reinitialize if inside a modal
            if ($element.closest('.modal').length) {
                // Skip if it's a quick booking field (shouldn't be in modal)
                if ($element.closest('.booking-form-section').length) {
                    return;
                }
                
                // Destroy existing if exists
                if ($element.hasClass('select2-hidden-accessible')) {
                    $element.select2('destroy');
                }
                
                $element.select2({
                    dropdownParent: $element.closest('.modal'),
                    ajax: {
                        url: '/airports/autocomplete/',
                        dataType: 'json',
                        delay: 300,
                        data: function(params) {
                            return { q: params.term };
                        },
                        processResults: function(data) {
                            var results = [];
                            if (data.results && Array.isArray(data.results)) {
                                results = data.results.map(function(item) {
                                    return {
                                        id: item.iata || item.id,
                                        text: item.text || (item.city + ' (' + (item.iata || item.id) + ')'),
                                        iata: item.iata,
                                        name: item.name,
                                        city: item.city,
                                        country: item.country
                                    };
                                });
                            }
                            return { results: results };
                        },
                        cache: true
                    },
                    minimumInputLength: 2,
                    placeholder: 'Search by city, airport name, or code...',
                    allowClear: true,
                    dropdownAutoWidth: false,
                    width: '100%',
                    templateResult: formatAirportResult,
                    templateSelection: formatAirportSelection
                });
                
                var hiddenInputId = $element.attr('id').replace('_display', '_iata');
                $element.on('select2:select', function(e) {
                    var data = e.params.data;
                    if (data && data.iata) {
                        $('#' + hiddenInputId).val(data.iata);
                    }
                });
                
                $element.on('select2:clear', function() {
                    $('#' + hiddenInputId).val('');
                });
            }
        });
    };
    
    // Listen for modal open events (for enquiry forms)
    $(document).on('shown.bs.modal', '.modal', function() {
        if (typeof window.reinitModalAutocomplete === 'function') {
            setTimeout(function() {
                window.reinitModalAutocomplete();
            }, 100);
        }
    });
});