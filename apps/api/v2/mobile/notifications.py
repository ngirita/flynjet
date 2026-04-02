from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from apps.core.models import Notification
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
def mobile_notifications(request):
    """Get user notifications (mobile optimized)"""
    # Get query parameters
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    unread_only = request.query_params.get('unread_only', 'false').lower() == 'true'
    
    # Filter notifications
    notifications = Notification.objects.filter(recipient=request.user)
    
    if unread_only:
        notifications = notifications.filter(is_read=False)
    
    notifications = notifications.order_by('-created_at')
    
    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    
    total = notifications.count()
    results = notifications[start:end]
    
    data = [{
        'id': str(n.id),
        'type': n.notification_type,
        'title': n.title,
        'message': n.message,
        'created_at': n.created_at.isoformat(),
        'is_read': n.is_read,
        'action_url': n.action_url
    } for n in results]
    
    return Response({
        'count': total,
        'unread_count': notifications.filter(is_read=False).count(),
        'next': page * page_size < total,
        'previous': page > 1,
        'results': data
    })


@api_view(['POST'])
def mobile_mark_read(request, notification_id):
    """Mark notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
    except Notification.DoesNotExist:
        return Response({
            'error': 'Notification not found'
        }, status=404)
    
    notification.mark_as_read()
    
    return Response({'status': 'read'})


@api_view(['POST'])
def mobile_mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    return Response({'status': 'all_read'})


@api_view(['DELETE'])
def mobile_delete_notification(request, notification_id):
    """Delete notification"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
    except Notification.DoesNotExist:
        return Response({
            'error': 'Notification not found'
        }, status=404)
    
    notification.delete()
    
    return Response({'status': 'deleted'})


@api_view(['POST'])
def mobile_register_push(request):
    """Register push notification token"""
    token = request.data.get('push_token')
    device_type = request.data.get('device_type', 'mobile')
    device_id = request.data.get('device_id')
    
    if not token:
        return Response({
            'error': 'Push token required'
        }, status=400)
    
    # Update user's device with push token
    if device_id:
        from apps.accounts.models import UserDevice
        device, created = UserDevice.objects.update_or_create(
            user=request.user,
            device_id=device_id,
            defaults={
                'push_notification_token': token,
                'device_type': device_type,
                'last_login': timezone.now()
            }
        )
    
    return Response({'status': 'registered'})