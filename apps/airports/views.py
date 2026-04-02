from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.db import models
from .models import Airport

class AirportAutocompleteView(ListView):
    """API endpoint for airport autocomplete"""
    model = Airport
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Airport.objects.filter(is_active=True)
        query = self.request.GET.get('q', '')
        
        if query and len(query) >= 2:
            queryset = queryset.filter(
                models.Q(name__icontains=query) |
                models.Q(city__icontains=query) |
                models.Q(iata_code__icontains=query) |
                models.Q(country__icontains=query)
            )
        
        return queryset
    
    def render_to_response(self, context, **response_kwargs):
        results = []
        for airport in context['object_list']:
            results.append({
                'id': airport.iata_code,
                'text': f"{airport.name} ({airport.iata_code}) - {airport.city}, {airport.country}",
                'iata': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country
            })
        
        return JsonResponse({
            'results': results,
            'pagination': {
                'more': context['page_obj'].has_next()
            }
        })

class AirportListView(ListView):
    """List all airports"""
    model = Airport
    template_name = 'airports/list.html'
    context_object_name = 'airports'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Airport.objects.filter(is_active=True)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(city__icontains=search) |
                models.Q(country__icontains=search) |
                models.Q(iata_code__icontains=search)
            )
        
        # Filter by country
        country = self.request.GET.get('country')
        if country:
            queryset = queryset.filter(country=country)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Airport.objects.filter(is_active=True).values_list('country', flat=True).distinct().order_by('country')
        return context

class AirportDetailView(DetailView):
    """Airport detail page"""
    model = Airport
    template_name = 'airports/detail.html'
    context_object_name = 'airport'
    slug_field = 'iata_code'
    slug_url_kwarg = 'iata_code'