import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db.models import Q, Count
from .models import Conversation, Message, ChatQueue

import logging
logger = logging.getLogger(__name__)


def _get_ai_welcome(conversation_id, user):
    """Return an AI welcome response using the shared module-level processor.

    FIXED: Previously init_chat created a brand-new NLPProcessor() on every
    request, bypassing the already-initialized module-level instance in
    consumers.py.  This caused inconsistent initialization state and wasted
    memory.  We now import and reuse the single shared instance.
    """
    from .consumers import _nlp_processor, _processor_initialized

    if _processor_initialized and _nlp_processor is not None:
        try:
            return _nlp_processor.process_message("hello", conversation_id, user)
        except Exception as e:
            logger.error(f"NLP processor error in _get_ai_welcome: {e}")

    # Fallback when processor isn't ready yet
    return {
        'response': (
            "Hello! Welcome to FlynJet Support. How can I help you today? "
            "I can assist with flight bookings, booking status, fleet information, and more."
        ),
        'intent': 'greeting',
        'confidence': 0.95,
        'suggestions': ['Book a flight', 'Check booking status', 'Fleet info', 'Talk to agent']
    }


@csrf_exempt
def init_chat(request):
    """Initialize a new chat conversation — ALWAYS starts with AI, no agent assigned."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    page_url = request.META.get('HTTP_REFERER', '')

    if request.user.is_authenticated:
        # Reuse an existing active AI-only conversation for this user
        conversation = Conversation.objects.filter(
            user=request.user,
            status='active',
            agent__isnull=True   # Only reuse conversations with no human agent
        ).order_by('-started_at').first()

        if not conversation:
            conversation = Conversation.objects.create(
                user=request.user,
                subject='Support Chat',
                status='active',
                agent=None,  # Explicitly no agent — AI handles from the start
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                page_url=page_url
            )
            created = True
            logger.info(f"Created new AI conversation for user: {conversation.conversation_id}")
        else:
            created = False
            logger.info(f"Reusing existing AI conversation: {conversation.conversation_id}")
    else:
        # Guest session — always create a fresh conversation
        conversation = Conversation.objects.create(
            subject='Support Chat',
            status='active',
            agent=None,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            page_url=page_url
        )
        created = True
        logger.info(f"Created new AI conversation for guest: {conversation.conversation_id}")

    # Only save a welcome message for brand-new conversations.
    # For reused conversations the history already contains the welcome message,
    # so we do NOT add another one (this was a source of duplicate welcomes).
    if created:
        auth_user = request.user if request.user.is_authenticated else None
        ai_response = _get_ai_welcome(conversation.conversation_id, auth_user)

        Message.objects.create(
            conversation=conversation,
            sender=None,
            sender_name='FlynJet Assistant',
            message=ai_response['response'],
            is_ai=True,
            is_agent=False,
            message_type='ai',
            intent=ai_response.get('intent', 'greeting'),
            confidence=ai_response.get('confidence', 0.95),
            suggested_responses=ai_response.get('suggestions', [])
        )
    else:
        # Pull suggestions from the last AI message for the UI
        last_ai = conversation.messages.filter(is_ai=True).order_by('-created_at').first()
        ai_response = {
            'response': last_ai.message if last_ai else '',
            'suggestions': last_ai.suggested_responses if last_ai else []
        }

    return JsonResponse({
        'conversation_id': conversation.conversation_id,
        'conversation_code': conversation.conversation_id,
        'created': created,
        'ws_url': f"/ws/chat/{conversation.conversation_id}/",
        'ai_welcome': ai_response.get('response', ''),
        'suggestions': ai_response.get('suggestions', []),
        'is_ai_mode': True
    })


class ChatWidgetView(TemplateView):
    """Chat widget for website"""
    template_name = 'chat/widget.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            conversation, created = Conversation.objects.get_or_create(
                user=self.request.user,
                status='active',
                defaults={'subject': 'Support Chat'}
            )
            context['conversation'] = conversation
            context['ws_url'] = f"ws://{self.request.get_host()}/ws/chat/{conversation.conversation_id}/"
        return context


class AgentDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Agent dashboard for managing chats"""
    template_name = 'chat/agent_dashboard.html'

    def test_func(self):
        user = self.request.user
        return user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        queue = ChatQueue.objects.select_related('conversation__user').filter(
            exited_at__isnull=True
        ).order_by('position')

        active = Conversation.objects.filter(
            status='active',
            agent=self.request.user
        )

        recent = Conversation.objects.filter(
            agent=self.request.user
        ).exclude(status='active')[:20]

        context['queue'] = queue
        context['active_conversations'] = active
        context['recent_conversations'] = recent
        context['ws_url'] = f"ws://{self.request.get_host()}/ws/agent/"

        return context


class ConversationView(LoginRequiredMixin, TemplateView):
    """Individual conversation view"""
    template_name = 'chat/conversation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation_id = self.kwargs.get('conversation_id')

        conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

        user = self.request.user
        if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent'] or user == conversation.user):
            messages.error(self.request, "You don't have permission to view this conversation")
            return redirect('core:home')

        messages_list = conversation.messages.all().order_by('created_at')

        context['conversation'] = conversation
        context['messages'] = messages_list
        context['ws_url'] = f"ws://{self.request.get_host()}/ws/chat/{conversation_id}/"

        return context


class ChatHistoryView(LoginRequiredMixin, ListView):
    """User's chat history"""
    model = Conversation
    template_name = 'chat/history.html'
    context_object_name = 'conversations'
    paginate_by = 20

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).order_by('-started_at')


@csrf_exempt
def agent_queue(request):
    """API endpoint for agent queue"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    queue = ChatQueue.objects.select_related('conversation__user').filter(
        exited_at__isnull=True
    ).order_by('position')

    data = [{
        'position': item.position,
        'conversation_id': item.conversation.conversation_id,
        'user': item.conversation.user.email if item.conversation.user else 'Guest',
        'subject': item.conversation.subject,
        'waiting_time': str(timezone.now() - item.entered_at).split('.')[0],
        'messages_count': item.conversation.messages.count()
    } for item in queue]

    return JsonResponse({'queue': data})


@csrf_exempt
def accept_conversation(request, conversation_id):
    """API endpoint for agent to accept conversation"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)
        conversation.assign_agent(request.user)

        ChatQueue.objects.filter(conversation=conversation).update(exited_at=timezone.now())

        return JsonResponse({
            'status': 'success',
            'conversation_id': conversation.conversation_id,
            'ws_url': f"ws://{request.get_host()}/ws/chat/{conversation_id}/"
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)


# ========== AGENT DASHBOARD API ENDPOINTS ==========

@login_required
@user_passes_test(lambda u: u.is_staff or getattr(u, 'user_type', '') in ['admin', 'agent'])
def agent_conversations(request):
    """Get all conversations for agent dashboard - FIXED"""
    
    # WAITING: Only conversations where user explicitly requested human agent
    # These have status='waiting' and no agent assigned
    waiting = Conversation.objects.filter(
        status='waiting',
        agent__isnull=True
    ).exclude(
        user=request.user  # Don't show agent's own conversations
    ).order_by('-started_at')
    
    # ACTIVE: Conversations assigned to THIS agent
    active = Conversation.objects.filter(
        agent=request.user,
        status='active'
    ).order_by('-started_at')
    
    # RESOLVED: Completed conversations (resolved or closed)
    resolved = Conversation.objects.filter(
        Q(agent=request.user) | Q(agent__isnull=True),
        status__in=['resolved', 'closed']
    ).exclude(
        user=request.user  # Also exclude own conversations from resolved
    ).order_by('-resolved_at')[:20]

    def serialize_conversation(conv):
        last_message = conv.messages.order_by('-created_at').first()
        unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()

        user_email = conv.user.email if conv.user else 'Guest'
        user_name = (
            (conv.user.get_full_name() or conv.user.email)
            if conv.user else 'Guest'
        )

        return {
            'conversation_id': conv.conversation_id,
            'user_email': user_email,
            'user_name': user_name,
            'subject': conv.subject,
            'status': conv.status,
            'created_at': conv.started_at.strftime('%Y-%m-%d %H:%M'),
            'last_message': last_message.message[:50] if last_message else 'No messages yet',
            'unread_count': unread_count
        }

    return JsonResponse({
        'waiting': [serialize_conversation(c) for c in waiting],
        'active': [serialize_conversation(c) for c in active],
        'resolved': [serialize_conversation(c) for c in resolved]
    })

@login_required
def conversation_messages(request, conversation_id):
    """Get messages for a specific conversation"""
    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    messages_list = conversation.messages.all().order_by('created_at')
    messages_list.filter(is_read=False).exclude(sender=user).update(
        is_read=True, read_at=timezone.now()
    )

    data = [{
        'id': str(msg.id),
        'message': msg.message,
        'sender_name': msg.sender_name,
        'is_agent': msg.is_agent,
        'is_ai': msg.is_ai,
        'created_at': msg.created_at.strftime('%H:%M')
    } for msg in messages_list]

    return JsonResponse(data, safe=False)

@csrf_exempt
@login_required
def mark_conversation_active(request, conversation_id):
    """
    Mark conversation as active when agent clicks on it.
    This assigns the agent and moves from waiting to active.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
    
    # Only proceed if conversation is waiting (needs agent) or already active with this agent
    if conversation.status == 'waiting' and conversation.agent is None:
        # Assign agent and make active
        conversation.agent = user
        conversation.status = 'active'
        conversation.first_response_at = timezone.now()
        if conversation.started_at:
            conversation.response_time = conversation.first_response_at - conversation.started_at
        conversation.save(update_fields=['agent', 'status', 'first_response_at', 'response_time'])
        
        # Remove from queue
        ChatQueue.objects.filter(conversation=conversation).delete()
        
        # Send notification to user via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{conversation.conversation_id}',
            {
                'type': 'agent_assigned',
                'agent_name': user.get_full_name() or user.email
            }
        )
        
        logger.info(f"Agent {user.email} accepted conversation {conversation_id}")
        
    elif conversation.status == 'active' and conversation.agent == user:
        # Already active with this agent, just refresh
        pass
    else:
        return JsonResponse({'error': 'Conversation not available for acceptance'}, status=400)
    
    return JsonResponse({'status': 'success'})


@login_required
def conversation_detail(request, conversation_id):
    """Get conversation details"""
    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    user_email = conversation.user.email if conversation.user else 'Guest'
    user_name = (
        (conversation.user.get_full_name() or conversation.user.email)
        if conversation.user else 'Guest'
    )

    return JsonResponse({
        'conversation_id': conversation.conversation_id,
        'user_email': user_email,
        'user_name': user_name,
        'subject': conversation.subject,
        'status': conversation.status,
        'priority': conversation.priority,
        'created_at': conversation.started_at.strftime('%Y-%m-%d %H:%M')
    })


@csrf_exempt
@login_required
def accept_conversation_api(request, conversation_id):
    """Accept a conversation (assign to current agent)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

    conversation.agent = user
    conversation.status = 'active'
    conversation.first_response_at = timezone.now()
    if conversation.started_at:
        conversation.response_time = conversation.first_response_at - conversation.started_at
    conversation.save(update_fields=['agent', 'status', 'first_response_at', 'response_time'])

    Message.objects.create(
        conversation=conversation,
        sender=user,
        sender_name=f"Agent {user.get_full_name() or user.email}",
        message=f"Agent {user.get_full_name() or user.email} has joined the conversation",
        is_agent=True,
        message_type='system'
    )

    ChatQueue.objects.filter(conversation=conversation).delete()

    return JsonResponse({'status': 'success'})


@csrf_exempt
@login_required
def resolve_conversation_api(request, conversation_id):
    """Mark conversation as resolved"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
    conversation.status = 'resolved'
    conversation.resolved_at = timezone.now()
    conversation.save(update_fields=['status', 'resolved_at'])

    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        sender_name=f"Agent {request.user.get_full_name() or request.user.email}",
        message="This conversation has been marked as resolved",
        is_agent=True,
        message_type='system'
    )

    return JsonResponse({'status': 'success'})


@csrf_exempt
@login_required
def close_conversation_api(request, conversation_id):
    """Close conversation and request rating from user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
    
    # Only agent or admin can close
    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent'] or user == conversation.agent):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    conversation.status = 'closed'
    conversation.closed_at = timezone.now()
    conversation.active_agent_viewing = None
    conversation.save(update_fields=['status', 'closed_at', 'active_agent_viewing'])

    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        sender_name=f"Agent {request.user.get_full_name() or request.user.email}",
        message="This conversation has been closed. Please rate your experience.",
        is_agent=True,
        message_type='system'
    )
    
    # Send rating request to user via WebSocket
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{conversation.conversation_id}',
        {
            'type': 'request_rating',
            'conversation_id': conversation.conversation_id,
            'message': 'How would you rate your support experience?'
        }
    )

    return JsonResponse({'status': 'success'})


@csrf_exempt
@login_required
def submit_rating_api(request, conversation_id):
    """Submit rating and reactivate AI"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        rating = data.get('rating')
        feedback = data.get('feedback', '')
    except json.JSONDecodeError:
        rating = request.POST.get('rating')
        feedback = request.POST.get('feedback', '')
    
    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
    
    # Verify user owns this conversation
    if request.user != conversation.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Save feedback
    from .models import ChatFeedback
    ChatFeedback.objects.create(
        conversation=conversation,
        rating=int(rating),
        comment=feedback,
        resolved_issue=int(rating) >= 3,
        agent_helpful=int(rating) >= 4
    )
    
    # Update conversation satisfaction
    conversation.satisfaction_rating = int(rating)
    conversation.satisfaction_feedback = feedback
    
    # Reactivate with AI (remove agent, set status to active)
    conversation.agent = None
    conversation.status = 'active'
    conversation.active_agent_viewing = None
    conversation.save(update_fields=['agent', 'status', 'active_agent_viewing', 'satisfaction_rating', 'satisfaction_feedback'])
    
    # Send AI welcome back message
    from .consumers import _nlp_processor, _processor_initialized
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    if _processor_initialized and _nlp_processor:
        ai_response = _nlp_processor.process_message("thank you for the feedback", conversation_id, conversation.user)
        
        ai_message = Message.objects.create(
            conversation=conversation,
            sender=None,
            sender_name='FlynJet Assistant',
            message=ai_response['response'],
            is_ai=True,
            intent=ai_response.get('intent', 'feedback'),
            confidence=ai_response.get('confidence', 0.95),
            suggested_responses=ai_response.get('suggestions', [])
        )
        
        # Send AI message to chat room
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{conversation.conversation_id}',
            {
                'type': 'chat_message',
                'message': {
                    'id': str(ai_message.id),
                    'sender': 'FlynJet Assistant',
                    'sender_name': 'FlynJet Assistant',
                    'message': ai_message.message,
                    'timestamp': ai_message.created_at.isoformat(),
                    'is_agent': False,
                    'is_ai': True,
                    'suggestions': ai_response.get('suggestions', [])
                }
            }
        )
    
    return JsonResponse({'status': 'success'})

@csrf_exempt
@login_required
def switch_to_ai_api(request, conversation_id):
    """Switch conversation back to AI assistant"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

    conversation.agent = None
    conversation.status = 'active'
    conversation.save(update_fields=['agent', 'status'])

    Message.objects.create(
        conversation=conversation,
        sender=user,
        sender_name=f"Agent {user.get_full_name() or user.email}",
        message=f"Agent {user.get_full_name() or user.email} has switched the conversation back to AI assistant",
        is_agent=True,
        message_type='system'
    )

    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{conversation.conversation_id}',
        {
            'type': 'switch_to_ai',
            'message': 'Conversation switched back to AI assistant'
        }
    )

    return JsonResponse({'status': 'success'})


@csrf_exempt
@login_required
def end_chat_api(request, conversation_id):
    """End conversation (close it) — called by the user themselves"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

    user = request.user
    if not (user.is_authenticated and user == conversation.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    conversation.status = 'closed'
    conversation.closed_at = timezone.now()
    conversation.save(update_fields=['status', 'closed_at'])

    Message.objects.create(
        conversation=conversation,
        sender=user,
        sender_name=user.get_full_name() or user.email,
        message="User has ended the conversation",
        is_agent=False,
        message_type='system'
    )

    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{conversation.conversation_id}',
        {
            'type': 'chat_ended',
            'message': 'The conversation has been ended by the user'
        }
    )

    return JsonResponse({'status': 'success'})


@csrf_exempt
def test_ai(request):
    """Test endpoint to check if AI is working"""
    if request.method == 'GET':
        try:
            from .consumers import _nlp_processor, _processor_initialized

            if not _processor_initialized or _nlp_processor is None:
                return JsonResponse({
                    'status': 'error',
                    'initialized': False,
                    'error': 'NLP processor not initialized'
                }, status=500)

            test_response = _nlp_processor.process_message("hello", None, None)

            return JsonResponse({
                'status': 'success',
                'initialized': _nlp_processor._is_initialized,
                'training_data_count': len(_nlp_processor.training_data),
                'test_response': test_response
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)

# VIEWS.PY ADDITIONS
# Add these new API endpoints

@csrf_exempt
@login_required
def mark_agent_viewing(request, conversation_id):
    """Mark that an agent is actively viewing this conversation"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    user = request.user
    if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
    
    # Mark agent as viewing
    conversation.active_agent_viewing = user
    conversation.agent_viewing_since = timezone.now()
    conversation.save(update_fields=['active_agent_viewing', 'agent_viewing_since'])
    
    # Send system message to notify user
    Message.objects.create(
        conversation=conversation,
        sender=None,
        sender_name='System',
        message=f"An agent is now viewing your conversation.",
        is_agent=True,
        is_ai=False,
        message_type='system'
    )
    
    # Notify via WebSocket
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{conversation.conversation_id}',
        {
            'type': 'chat_message',
            'message': {
                'id': 'system',
                'sender': 'System',
                'sender_name': 'System',
                'message': 'An agent is now viewing your conversation.',
                'timestamp': timezone.now().isoformat(),
                'is_agent': True,
                'is_ai': False
            }
        }
    )
    
    logger.info(f"Agent {user.email} now viewing conversation {conversation_id}")
    
    return JsonResponse({'status': 'success'})


@csrf_exempt
@login_required
def unmark_agent_viewing(request, conversation_id):
    """Unmark agent viewing (when they close the conversation)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
    
    # Only allow the viewing agent or staff to unmark
    user = request.user
    if conversation.active_agent_viewing == user or user.is_staff:
        conversation.active_agent_viewing = None
        conversation.agent_viewing_since = None
        conversation.save(update_fields=['active_agent_viewing', 'agent_viewing_since'])
        
        logger.info(f"Agent viewing unmarked for conversation {conversation_id}")
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'error': 'Unauthorized'}, status=403)

