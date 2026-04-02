# apps/core/views_admin.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import AdminNotification
import logging

logger = logging.getLogger(__name__)


def get_time_ago(dt):
    """Get human readable time ago"""
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 365:
        return f"{diff.days // 365} years ago"
    elif diff.days > 30:
        return f"{diff.days // 30} months ago"
    elif diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minutes ago"
    else:
        return "just now"


@staff_member_required
def admin_notifications_api(request):
    """API endpoint for admin notifications"""
    # Get unread count
    unread_count = AdminNotification.objects.filter(is_read=False).count()
    
    # Get recent notifications (last 20)
    notifications = AdminNotification.objects.all()[:20]
    
    data = {
        'unread_count': unread_count,
        'notifications': [{
            'id': str(n.id),
            'notification_type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'link': n.link,
            'is_read': n.is_read,
            'time_ago': get_time_ago(n.created_at),
            'created_at': n.created_at.isoformat(),
        } for n in notifications]
    }
    return JsonResponse(data)


@staff_member_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        notification = AdminNotification.objects.get(id=notification_id)
        notification.mark_as_read()
        return JsonResponse({'status': 'success'})
    except AdminNotification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)


@staff_member_required
@csrf_exempt
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        count = AdminNotification.objects.filter(is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success', 'count': count})
    return JsonResponse({'status': 'error'}, status=405)


@staff_member_required
def get_enquiry_data(request, enquiry_id):
    """API endpoint to get enquiry data for auto-filling contracts"""
    from apps.fleet.models import Enquiry
    import datetime
    
    try:
        enquiry = Enquiry.objects.get(id=enquiry_id)
        
        data = {
            'enquiry_number': enquiry.enquiry_number,
            'client_name': enquiry.get_full_name(),
            'client_email': enquiry.email,
            'client_phone': enquiry.phone,
            'aircraft_id': str(enquiry.aircraft.id) if enquiry.aircraft else '',
            'passenger_count': enquiry.passenger_count,
            'luggage_weight_kg': float(enquiry.luggage_weight_kg),
            'departure_airport': enquiry.departure_airport or '',
            'arrival_airport': enquiry.arrival_airport or '',
            'valid_until': (timezone.now() + timezone.timedelta(days=7)).strftime('%Y-%m-%d'),
        }
        
        if enquiry.preferred_departure_date:
            dt = datetime.datetime.combine(enquiry.preferred_departure_date, datetime.time(12, 0))
            data['departure_datetime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        if enquiry.preferred_return_date:
            dt = datetime.datetime.combine(enquiry.preferred_return_date, datetime.time(16, 0))
            data['arrival_datetime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return JsonResponse(data)
        
    except Enquiry.DoesNotExist:
        return JsonResponse({'error': f'Enquiry with ID {enquiry_id} not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_enquiry_data: {e}")
        return JsonResponse({'error': str(e)}, status=500)