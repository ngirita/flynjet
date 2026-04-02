from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from .models import Conversation, Message, ChatQueue, ChatBotTraining
from .ai.nlp import NLPProcessor, IntentClassifier
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_waiting_queue():
    """Process waiting conversations and assign agents"""
    queue = ChatQueue.objects.filter(exited_at__isnull=True).order_by('position')
    
    # Get available agents
    from apps.accounts.models import User
    available_agents = User.objects.filter(
        user_type__in=['agent', 'admin'],
        is_active=True
    )
    
    # Simple round-robin assignment
    if available_agents.exists() and queue.exists():
        agent_index = 0
        for queue_item in queue:
            if agent_index < available_agents.count():
                agent = available_agents[agent_index]
                queue_item.conversation.assign_agent(agent)
                agent_index += 1
            else:
                break
    
    logger.info(f"Processed waiting queue: {queue.count()} items")
    return queue.count()

@shared_task
def send_chat_transcript(conversation_id, email):
    """Send chat transcript via email"""
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        messages = conversation.messages.all().order_by('created_at')
        
        # Generate transcript
        transcript = f"Chat Transcript - {conversation.conversation_id}\n"
        transcript += f"Date: {conversation.started_at.strftime('%Y-%m-%d %H:%M')}\n"
        transcript += f"User: {conversation.user.email}\n"
        transcript += f"Agent: {conversation.agent.email if conversation.agent else 'None'}\n\n"
        
        for msg in messages:
            sender = msg.sender_name or (msg.sender.email if msg.sender else 'System')
            transcript += f"[{msg.created_at.strftime('%H:%M')}] {sender}: {msg.message}\n"
        
        # Send email
        send_mail(
            f'Chat Transcript - {conversation.conversation_id}',
            transcript,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        logger.info(f"Chat transcript sent for conversation {conversation_id}")
        return True
    except Conversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return False

@shared_task
def train_chatbot():
    """Train chatbot with latest data"""
    from .ai.nlp import NLPProcessor
    
    processor = NLPProcessor()
    processor.train()
    
    logger.info("Chatbot training completed")
    return True

@shared_task
def cleanup_old_conversations(days=30):
    """Archive old conversations"""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    old_conversations = Conversation.objects.filter(
        closed_at__lt=cutoff,
        status='closed'
    )
    
    count = old_conversations.count()
    # Archive logic here
    
    logger.info(f"Cleaned up {count} old conversations")
    return count

@shared_task
def analyze_conversation_sentiment(conversation_id):
    """Analyze sentiment of conversation"""
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        messages = conversation.messages.filter(is_ai=False).values_list('message', flat=True)
        
        if messages:
            from .ai.nlp import NLPProcessor
            processor = NLPProcessor()
            
            # Aggregate sentiment
            sentiments = []
            for msg in messages:
                sentiment = processor.analyze_sentiment(msg)
                sentiments.append(sentiment)
            
            if sentiments:
                conversation.sentiment = sum(sentiments) / len(sentiments)
                conversation.save(update_fields=['sentiment'])
                
                logger.info(f"Sentiment analyzed for conversation {conversation_id}: {conversation.sentiment}")
        
        return True
    except Conversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return False

@shared_task
def generate_chat_report(days=7):
    """Generate chat statistics report"""
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    conversations = Conversation.objects.filter(created_at__gte=start_date)
    
    report = {
        'period_days': days,
        'total_conversations': conversations.count(),
        'resolved': conversations.filter(status='resolved').count(),
        'avg_response_time': conversations.filter(
            first_response_at__isnull=False
        ).aggregate(avg=models.Avg('response_time'))['avg'],
        'avg_rating': conversations.filter(
            satisfaction_rating__isnull=False
        ).aggregate(avg=models.Avg('satisfaction_rating'))['avg'],
        'by_status': dict(conversations.values_list('status').annotate(count=models.Count('id'))),
    }
    
    logger.info(f"Chat report generated: {report}")
    return report