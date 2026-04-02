import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import FlightTrack, TrackingPosition
import logging

logger = logging.getLogger(__name__)

class TrackingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time flight tracking"""
    
    async def connect(self):
        self.booking_id = self.scope['url_route']['kwargs']['booking_id']
        self.room_group_name = f'track_{self.booking_id}'
        
        # Check if user has permission
        if not await self.has_permission():
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
        
        logger.info(f"WebSocket connected for booking {self.booking_id}")
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected for booking {self.booking_id}")
    
    async def receive(self, text_data):
        """Receive message from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))
            
            elif message_type == 'request_update':
                await self.send_initial_data()
            
            elif message_type == 'set_alert':
                await self.handle_set_alert(data)
            
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def send_initial_data(self):
        """Send initial tracking data"""
        track = await self.get_track_data()
        if track:
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': track
            }))
    
    async def position_update(self, event):
        """Send position update to client"""
        await self.send(text_data=json.dumps({
            'type': 'position_update',
            'data': event['data']
        }))
    
    async def status_update(self, event):
        """Send status update to client"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'data': event['data']
        }))
    
    async def notification(self, event):
        """Send notification to client"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }))
    
    @database_sync_to_async
    def has_permission(self):
        """Check if user has permission to view this tracking"""
        user = self.scope['user']
        if not user.is_authenticated:
            return False
        
        try:
            track = FlightTrack.objects.get(booking_id=self.booking_id)
            return (
                user.is_staff or
                user == track.booking.user or
                user.user_type in ['admin', 'agent']
            )
        except FlightTrack.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_track_data(self):
        """Get current tracking data"""
        try:
            track = FlightTrack.objects.select_related('booking').get(booking_id=self.booking_id)
            return {
                'flight_number': track.flight_number,
                'aircraft': track.aircraft_registration,
                'latitude': track.latitude,
                'longitude': track.longitude,
                'altitude': track.altitude,
                'heading': track.heading,
                'speed': track.speed,
                'progress': track.progress_percentage,
                'departure': {
                    'airport': track.departure_airport,
                    'name': track.departure_airport_name,
                    'time': track.departure_time.isoformat() if track.departure_time else None
                },
                'arrival': {
                    'airport': track.arrival_airport,
                    'name': track.arrival_airport_name,
                    'estimated': track.estimated_arrival.isoformat() if track.estimated_arrival else None,
                    'scheduled': track.arrival_time.isoformat() if track.arrival_time else None
                },
                'weather': track.weather,
                'last_update': track.last_update.isoformat() if track.last_update else None,
                'is_tracking': track.is_tracking
            }
        except FlightTrack.DoesNotExist:
            return None
    
    @database_sync_to_async
    def handle_set_alert(self, data):
        """Handle setting an alert"""
        from .models import FlightAlert
        try:
            track = FlightTrack.objects.get(booking_id=self.booking_id)
            alert, created = FlightAlert.objects.get_or_create(
                track=track,
                user=self.scope['user'],
                alert_type=data.get('alert_type'),
                defaults={
                    'threshold_value': data.get('threshold'),
                    'custom_message': data.get('message', ''),
                    'notify_email': data.get('notify_email', True),
                    'notify_push': data.get('notify_push', False),
                    'notify_sms': data.get('notify_sms', False)
                }
            )
            return {'success': True, 'created': created}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class TrackingShareConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for shared tracking links"""
    
    async def connect(self):
        self.token = self.scope['url_route']['kwargs']['token']
        self.room_group_name = f'share_{self.token}'
        
        # Validate share token
        if not await self.validate_share():
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Record view
        await self.record_view()
        
        # Send initial data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def position_update(self, event):
        """Send position update to client"""
        await self.send(text_data=json.dumps({
            'type': 'position_update',
            'data': event['data']
        }))
    
    @database_sync_to_async
    def validate_share(self):
        """Validate share token"""
        from .models import TrackingShare
        try:
            share = TrackingShare.objects.get(token=self.token)
            if share.is_valid():
                self.track = share.track
                return True
            return False
        except TrackingShare.DoesNotExist:
            return False
    
    @database_sync_to_async
    def record_view(self):
        """Record view of shared link"""
        from .models import TrackingShare
        try:
            share = TrackingShare.objects.get(token=self.token)
            share.record_view()
        except TrackingShare.DoesNotExist:
            pass
    
    @database_sync_to_async
    def get_track_data(self):
        """Get tracking data for share"""
        if not self.track:
            return None
        
        return {
            'flight_number': self.track.flight_number,
            'aircraft': self.track.aircraft_registration,
            'latitude': self.track.latitude,
            'longitude': self.track.longitude,
            'altitude': self.track.altitude,
            'heading': self.track.heading,
            'speed': self.track.speed,
            'progress': self.track.progress_percentage,
            'departure': self.track.departure_airport,
            'arrival': self.track.arrival_airport,
            'estimated_arrival': self.track.estimated_arrival.isoformat() if self.track.estimated_arrival else None,
            'last_update': self.track.last_update.isoformat() if self.track.last_update else None
        }
    
    async def send_initial_data(self):
        """Send initial tracking data"""
        data = await self.get_track_data()
        if data:
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': data
            }))