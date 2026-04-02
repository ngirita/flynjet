from django import forms
from django.urls import reverse_lazy

class AirportAutocompleteWidget(forms.TextInput):
    """
    A widget that provides autocomplete for airports.
    Users can type city or airport name, and it returns IATA code internally.
    """
    template_name = 'widgets/airport_autocomplete.html'
    
    class Media:
        css = {
            'all': ('https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css',)
        }
        js = (
            'https://code.jquery.com/jquery-3.6.0.min.js',
            'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js',
            'js/airport-autocomplete.js',
        )
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'airport-autocomplete',
            'data-autocomplete-url': reverse_lazy('airports:autocomplete'),
            'placeholder': 'Search by city or airport name...',
            'style': 'width: 100%;'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)