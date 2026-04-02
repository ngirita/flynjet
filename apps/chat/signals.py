from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models
from .models import Conversation, Message, ChatQueue
from apps.core.models import Notification
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def handle_new_message(sender, instance, created, **kwargs):
    """Handle new message created"""
    if created:
        conversation = instance.conversation

        # Update conversation last activity
        conversation.save()  # This updates updated_at

        # FIXED: Removed auto-queue logic that was firing on every user message.
        # Conversations should only enter the queue when the user explicitly
        # requests a human agent via the 'transfer' WebSocket message type or
        # when the NLP processor detects intent == 'agent' with agent keywords.
        # Auto-queuing here caused every conversation to immediately get
        # status='waiting', which blocked the AI from responding.

        if instance.is_agent:
            # Notify user that agent responded
            notify_user_about_agent_response(conversation, instance)
        elif conversation.agent:
            # Notify the assigned agent about a new user message
            notify_agent_about_new_message(conversation, instance)
        # No else branch — do NOT notify/queue when there is no agent and
        # the message is a regular user message. The AI handles it directly.


def notify_admins_about_new_chat(conversation, message):
    """Notify all admins and available agents about new chat.
    Called explicitly from consumers.py when a user requests an agent,
    NOT automatically on every message.
    """
    from apps.accounts.models import User

    # Guard: conversation.user may be None for guest sessions
    user_display = conversation.user.email if conversation.user else 'Guest'
    message_preview = message.message[:50] if message and message.message else ''

    admin_users = User.objects.filter(
        models.Q(user_type__in=['admin', 'agent']) | models.Q(is_staff=True),
        is_active=True
    )

    for admin in admin_users:
        Notification.objects.create(
            recipient=admin,
            notification_type='chat',
            priority='high',
            title='New Chat Request',
            message=f'New chat from {user_display}: "{message_preview}..."',
            action_url='/chat/agent/',
            related_object=conversation,
            is_read=False
        )

        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'user_{admin.id}_notifications',
                {
                    'type': 'notification',
                    'data': {
                        'title': 'New Chat Request',
                        'message': f'New chat from {user_display}',
                        'conversation_id': conversation.conversation_id,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to send real-time notification: {e}")

    logger.info(f"Notified {admin_users.count()} admins about new chat {conversation.conversation_id}")


def notify_admins_about_waiting_message(conversation, message):
    """Notify admins about a waiting message when no agent is assigned.
    Called explicitly when a conversation enters the queue, not on every message.
    """
    from apps.accounts.models import User

    user_display = conversation.user.email if conversation.user else 'Guest'
    message_preview = message.message[:50] if message and message.message else ''

    admin_users = User.objects.filter(
        models.Q(user_type__in=['admin', 'agent']) | models.Q(is_staff=True),
        is_active=True
    )

    for admin in admin_users:
        # Avoid spamming: only notify once per 5-minute window per conversation
        recent_notification = Notification.objects.filter(
            recipient=admin,
            title='New Message in Queue',
            created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).exists()

        if not recent_notification:
            Notification.objects.create(
                recipient=admin,
                notification_type='chat',
                priority='medium',
                title='New Message in Queue',
                message=f'New message from {user_display} waiting for agent: "{message_preview}..."',
                action_url='/chat/agent/',
                related_object=conversation,
                is_read=False
            )


def notify_agent_about_new_message(conversation, message):
    """Notify the assigned agent about a new user message."""
    if not conversation.agent:
        return

    user_display = conversation.user.email if conversation.user else 'Guest'
    message_preview = message.message[:50] if message and message.message else ''

    Notification.objects.create(
        recipient=conversation.agent,
        notification_type='chat',
        priority='medium',
        title='New Message',
        message=f'New message from {user_display}: "{message_preview}..."',
        action_url=f'/chat/conversation/{conversation.conversation_id}/',
        related_object=conversation,
        is_read=False
    )


def notify_user_about_agent_response(conversation, message):
    """Notify the user about an agent response."""
    # Guard: guest conversations have no user to notify
    if not conversation.user:
        return

    message_preview = message.message[:50] if message and message.message else ''

    Notification.objects.create(
        recipient=conversation.user,
        notification_type='chat',
        priority='normal',
        title='New Response',
        message=f'Agent responded: "{message_preview}..."',
        action_url=f'/chat/conversation/{conversation.conversation_id}/',
        related_object=conversation,
        is_read=False
    )