from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg
from .models import Review, Testimonial, ReviewSummary
from .serializers import (
    ReviewSerializer, ReviewDetailSerializer,
    TestimonialSerializer, ReviewSummarySerializer
)

class ReviewViewSet(viewsets.ModelViewSet):
    """API for reviews"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Review.objects.all()
        return Review.objects.filter(status__in=['approved', 'featured'])
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        return ReviewSerializer
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_aircraft(self, request):
        """Get reviews for specific aircraft"""
        aircraft_id = request.query_params.get('aircraft_id')
        if not aircraft_id:
            return Response({'error': 'aircraft_id required'}, status=400)
        
        reviews = self.get_queryset().filter(aircraft_id=aircraft_id)
        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Vote on review"""
        review = self.get_object()
        vote_type = request.data.get('vote_type')
        
        if vote_type not in ['helpful', 'not_helpful']:
            return Response({'error': 'Invalid vote type'}, status=400)
        
        # Simplified voting - implement proper vote tracking in production
        if vote_type == 'helpful':
            review.helpful_votes += 1
        else:
            review.not_helpful_votes += 1
        
        review.save()
        
        return Response({
            'helpful': review.helpful_votes,
            'not_helpful': review.not_helpful_votes
        })


class TestimonialViewSet(viewsets.ReadOnlyModelViewSet):
    """API for testimonials"""
    serializer_class = TestimonialSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        return Testimonial.objects.filter(is_verified=True).order_by('-is_featured')


class ReviewSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """API for review summaries"""
    serializer_class = ReviewSummarySerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        return ReviewSummary.objects.all().order_by('-period_end')
    
    @action(detail=False, methods=['get'])
    def for_aircraft(self, request):
        """Get summary for specific aircraft"""
        aircraft_id = request.query_params.get('aircraft_id')
        if not aircraft_id:
            return Response({'error': 'aircraft_id required'}, status=400)
        
        summary = ReviewSummary.objects.filter(
            aircraft_id=aircraft_id
        ).order_by('-period_end').first()
        
        if summary:
            serializer = self.get_serializer(summary)
            return Response(serializer.data)
        
        return Response({'error': 'No summary found'}, status=404)