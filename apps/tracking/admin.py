# apps/tracking/admin.py - Add admin actions
from django.urls import path
from django.contrib import admin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from .models import FlightTrack, TrackingPosition, TrackingNotification, TrackingShare, FlightAlert
import json

@admin.register(FlightTrack)
class FlightTrackAdmin(admin.ModelAdmin):
    list_display = ['flight_number', 'booking', 'status', 'cargo_status', 'is_tracking', 'last_update']
    list_filter = ['is_tracking', 'data_source', 'status', 'cargo_status']
    search_fields = ['flight_number', 'aircraft_registration', 'booking__booking_reference']
    readonly_fields = ['created_at', 'updated_at', 'share_token']
    actions = ['mark_departed', 'mark_arrived', 'mark_delayed', 'update_position', 'update_cargo_status']
    
    fieldsets = (
        ('Flight Information', {
            'fields': ('booking', 'flight_number', 'aircraft_registration', 'data_source', 'status', 'remarks')
        }),
        ('Cargo Information', {
            'fields': ('cargo_status', 'cargo_manifest', 'cargo_weight'),
            'classes': ('collapse',)
        }),
        ('Current Position', {
            'fields': ('latitude', 'longitude', 'altitude', 'heading', 'speed')
        }),
        ('Flight Progress', {
            'fields': ('departure_time', 'arrival_time', 'estimated_arrival', 'actual_departure', 'actual_arrival',
                      'delay_minutes', 'progress_percentage', 'distance_remaining', 'time_remaining')
        }),
        ('Route', {
            'fields': ('departure_airport', 'arrival_airport', 'route', 'alternate_airports')
        }),
        ('Weather', {
            'fields': ('weather',)
        }),
        ('Sharing', {
            'fields': ('share_token', 'share_expiry')
        }),
        ('Timestamps', {
            'fields': ('last_update', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def mark_departed(self, request, queryset):
        """Mark selected flights as departed"""
        from django.utils import timezone
        
        for track in queryset:
            track.status = 'departed'
            track.actual_departure = timezone.now()
            track.is_tracking = True
            track.save()
            
            # Create notification
            TrackingNotification.objects.create(
                track=track,
                notification_type='departure',
                title='Flight Departed',
                message=f'Flight {track.flight_number} has departed from {track.departure_airport}',
                send_email=True
            )
        
        self.message_user(request, f'{queryset.count()} flights marked as departed.')
    mark_departed.short_description = "Mark selected flights as DEPARTED"
    
    def mark_arrived(self, request, queryset):
        """Mark selected flights as arrived"""
        from django.utils import timezone
        
        for track in queryset:
            track.status = 'arrived'
            track.actual_arrival = timezone.now()
            track.progress_percentage = 100
            track.is_tracking = False
            track.save()
            
            # Create notification
            TrackingNotification.objects.create(
                track=track,
                notification_type='arrival',
                title='Flight Arrived',
                message=f'Flight {track.flight_number} has arrived at {track.arrival_airport}',
                send_email=True
            )
        
        self.message_user(request, f'{queryset.count()} flights marked as arrived.')
    mark_arrived.short_description = "Mark selected flights as ARRIVED"
    
    def mark_delayed(self, request, queryset):
        """Mark selected flights as delayed"""
        return HttpResponseRedirect(reverse('admin:tracking_flighttrack_delay', args=[','.join(str(t.id) for t in queryset)]))
    mark_delayed.short_description = "Mark selected flights as DELAYED"
    
    def update_position(self, request, queryset):
        """Update position for selected flights"""
        if queryset.count() == 1:
            return HttpResponseRedirect(reverse('admin:tracking_flighttrack_update_position', args=[queryset.first().id]))
        else:
            self.message_user(request, 'Please select only one flight to update position.', level='ERROR')
    update_position.short_description = "Update position for selected flight"
    
    def update_cargo_status(self, request, queryset):
        """Update cargo status for selected flights"""
        return HttpResponseRedirect(reverse('admin:tracking_flighttrack_update_cargo', args=[','.join(str(t.id) for t in queryset)]))
    update_cargo_status.short_description = "Update cargo status"


@admin.register(TrackingPosition)
class TrackingPositionAdmin(admin.ModelAdmin):
    list_display = ['track', 'timestamp', 'latitude', 'longitude', 'altitude']
    list_filter = ['timestamp']
    search_fields = ['track__flight_number']
    readonly_fields = ['timestamp']

@admin.register(TrackingNotification)
class TrackingNotificationAdmin(admin.ModelAdmin):
    list_display = ['track', 'notification_type', 'title', 'is_sent', 'created_at']
    list_filter = ['notification_type', 'is_sent', 'created_at']
    search_fields = ['track__flight_number', 'title']
    readonly_fields = ['created_at', 'sent_at']

@admin.register(TrackingShare)
class TrackingShareAdmin(admin.ModelAdmin):
    list_display = ['track', 'token', 'created_by', 'expires_at', 'views']
    list_filter = ['expires_at']
    search_fields = ['track__flight_number', 'created_by__email']
    readonly_fields = ['token', 'created_at', 'last_viewed']

@admin.register(FlightAlert)
class FlightAlertAdmin(admin.ModelAdmin):
    list_display = ['track', 'user', 'alert_type', 'is_active', 'last_triggered']
    list_filter = ['alert_type', 'is_active']
    search_fields = ['track__flight_number', 'user__email']
    readonly_fields = ['last_triggered', 'trigger_count', 'created_at']

class FlightTrackAdminWithCustomViews(FlightTrackAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('delay/<str:ids>/', self.admin_site.admin_view(self.delay_view), name='tracking_flighttrack_delay'),
            path('update-position/<uuid:track_id>/', self.admin_site.admin_view(self.update_position_view), name='tracking_flighttrack_update_position'),
            path('update-cargo/<str:ids>/', self.admin_site.admin_view(self.update_cargo_view), name='tracking_flighttrack_update_cargo'),
        ]
        return custom_urls + urls
    
    def delay_view(self, request, ids):
        """View for setting delay minutes"""
        from django.utils import timezone
        
        track_ids = ids.split(',')
        tracks = FlightTrack.objects.filter(id__in=track_ids)
        
        if request.method == 'POST':
            delay_minutes = int(request.POST.get('delay_minutes', 0))
            delay_reason = request.POST.get('delay_reason', '')
            
            for track in tracks:
                track.status = 'delayed'
                track.delay_minutes = delay_minutes
                track.remarks = delay_reason
                
                # Update estimated arrival
                if track.estimated_arrival:
                    track.estimated_arrival = track.estimated_arrival + timezone.timedelta(minutes=delay_minutes)
                
                track.save()
                
                # Create notification
                TrackingNotification.objects.create(
                    track=track,
                    notification_type='delay',
                    title='Flight Delayed',
                    message=f'Flight {track.flight_number} is delayed by {delay_minutes} minutes. Reason: {delay_reason}',
                    send_email=True
                )
            
            self.message_user(request, f'{tracks.count()} flights delayed by {delay_minutes} minutes.')
            return HttpResponseRedirect(reverse('admin:tracking_flighttrack_changelist'))
        
        context = {
            'title': 'Set Delay',
            'tracks': tracks,
            'ids': ids,
        }
        return render(request, 'admin/tracking/delay_form.html', context)
    
    def update_position_view(self, request, track_id):
        """View for updating flight position manually"""
        track = get_object_or_404(FlightTrack, id=track_id)
        
        if request.method == 'POST':
            latitude = float(request.POST.get('latitude', 0))
            longitude = float(request.POST.get('longitude', 0))
            altitude = float(request.POST.get('altitude', 0)) if request.POST.get('altitude') else None
            speed = float(request.POST.get('speed', 0)) if request.POST.get('speed') else None
            heading = float(request.POST.get('heading', 0)) if request.POST.get('heading') else None
            
            track.update_position(
                latitude=latitude,
                longitude=longitude,
                altitude=altitude,
                speed=speed,
                heading=heading
            )
            
            # Update status based on position
            if track.status == 'scheduled' and altitude and altitude > 1000:
                track.status = 'in_air'
                track.actual_departure = timezone.now()
                track.save()
                
                TrackingNotification.objects.create(
                    track=track,
                    notification_type='departure',
                    title='Flight Departed',
                    message=f'Flight {track.flight_number} is now airborne',
                    send_email=True
                )
            elif track.status == 'in_air' and track.arrival_airport and track.progress_percentage >= 98:
                track.status = 'landed'
                track.save()
            
            self.message_user(request, f'Position updated for {track.flight_number}')
            return HttpResponseRedirect(reverse('admin:tracking_flighttrack_changelist'))
        
        context = {
            'title': f'Update Position - {track.flight_number}',
            'track': track,
        }
        return render(request, 'admin/tracking/update_position.html', context)
    
    def update_cargo_view(self, request, ids):
        """View for updating cargo status"""
        track_ids = ids.split(',')
        tracks = FlightTrack.objects.filter(id__in=track_ids)
        
        if request.method == 'POST':
            cargo_status = request.POST.get('cargo_status')
            cargo_notes = request.POST.get('cargo_notes', '')
            
            for track in tracks:
                track.cargo_status = cargo_status
                track.remarks = cargo_notes
                track.save()
                
                # Create cargo notification
                TrackingNotification.objects.create(
                    track=track,
                    notification_type='position',
                    title=f'Cargo Update - {track.get_cargo_status_display()}',
                    message=f'Cargo for flight {track.flight_number} is now {track.get_cargo_status_display()}. {cargo_notes}',
                    send_email=True
                )
            
            self.message_user(request, f'Cargo status updated for {tracks.count()} flights.')
            return HttpResponseRedirect(reverse('admin:tracking_flighttrack_changelist'))
        
        context = {
            'title': 'Update Cargo Status',
            'tracks': tracks,
            'ids': ids,
            'cargo_status_choices': FlightTrack._meta.get_field('cargo_status').choices,
        }
        return render(request, 'admin/tracking/update_cargo.html', context)

# Replace the admin registration
admin.site.unregister(FlightTrack)
admin.site.register(FlightTrack, FlightTrackAdminWithCustomViews)
