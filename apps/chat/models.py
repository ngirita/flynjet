import uuid
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import JSONField
from apps.core.models import TimeStampedModel
from apps.accounts.models import User
from apps.bookings.models import Booking

class Conversation(TimeStampedModel):
    """Chat conversation between user and support"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('waiting', 'Waiting for Agent'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Participants
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True,
        blank=True,
        related_name='chat_conversations'
    )
    agent = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_conversations'
    )
    
    # FIXED: Agent actively viewing (separate from assignment)
    active_agent_viewing = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actively_viewing_conversations',
        help_text='Agent currently viewing this conversation'
    )
    agent_viewing_since = models.DateTimeField(null=True, blank=True)

    # Conversation Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    subject = models.CharField(max_length=200)
    
    # Related Objects
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    
    # AI/ML Data
    intent = models.CharField(max_length=100, blank=True)
    confidence = models.FloatField(default=0.0)
    sentiment = models.FloatField(null=True, blank=True, help_text="Sentiment score -1 to 1")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    page_url = models.URLField(blank=True)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    response_time = models.DurationField(null=True, blank=True)
    
    # Satisfaction
    satisfaction_rating = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    satisfaction_feedback = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['conversation_id']),
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['active_agent_viewing']),
        ]
    
    def __str__(self):
        if self.user:
            return f"Conversation {self.conversation_id} - {self.user.email}"
        return f"Conversation {self.conversation_id} - Guest User"
        
    def save(self, *args, **kwargs):
        if not self.conversation_id:
            self.conversation_id = self.generate_conversation_id()
        super().save(*args, **kwargs)
    
    def generate_conversation_id(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"CHAT{timestamp}{random_str}"
    
    def assign_agent(self, agent):
        """Assign an agent to this conversation"""
        self.agent = agent
        self.active_agent_viewing = agent  # Also mark as viewing
        self.status = 'active'
        self.first_response_at = timezone.now()
        if self.started_at:
            self.response_time = self.first_response_at - self.started_at
        self.save(update_fields=['agent', 'active_agent_viewing', 'status', 'first_response_at', 'response_time'])
        
        # Create system message
        Message.objects.create(
            conversation=self,
            sender=agent,
            message=f"Agent {agent.get_full_name()} has joined the conversation",
            is_system=True
        )
    
    def resolve(self):
        """Mark conversation as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
    
    def close(self):
        """Close the conversation"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.active_agent_viewing = None  # Clear viewing when closing
        self.save(update_fields=['status', 'closed_at', 'active_agent_viewing'])
    
    def escalate(self, reason=""):
        """Escalate conversation to higher priority"""
        self.status = 'escalated'
        self.priority = 'high'
        self.save(update_fields=['status', 'priority'])
        
        # Notify all admins using core Notification model
        from apps.accounts.models import User
        from apps.core.models import Notification
        
        admin_users = User.objects.filter(
            models.Q(user_type='admin') | models.Q(is_staff=True),
            is_active=True
        )
        
        for admin in admin_users:
            Notification.objects.create(
                recipient=admin,
                notification_type='system',
                priority='urgent',
                title='Conversation Escalated',
                message=f"Conversation {self.conversation_id} escalated: {reason}",
                action_url=f"/chat/conversation/{self.conversation_id}/",
                related_object=self,
                is_read=False
            )


class Message(TimeStampedModel):
    """Individual messages in a conversation"""
    
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
        ('ai', 'AI Response'),
        ('typing', 'Typing Indicator'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    
    # Sender
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    sender_name = models.CharField(max_length=255, blank=True)
    is_agent = models.BooleanField(default=False)
    is_ai = models.BooleanField(default=False)
    
    # Message Content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    message = models.TextField()
    html_message = models.TextField(blank=True)
    
    # Attachments
    attachment = models.FileField(upload_to='chat_attachments/%Y/%m/%d/', blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.IntegerField(default=0)
    attachment_type = models.CharField(max_length=100, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # AI Metadata
    intent = models.CharField(max_length=100, blank=True)
    confidence = models.FloatField(default=0.0)
    suggested_responses = models.JSONField(default=list, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f"Message in {self.conversation.conversation_id} at {self.created_at}"
    
    def mark_as_read(self):
        """Mark message as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_delivered(self):
        """Mark message as delivered"""
        self.is_delivered = True
        self.delivered_at = timezone.now()
        self.save(update_fields=['is_delivered', 'delivered_at'])


class ChatQueue(models.Model):
    """Queue for waiting conversations"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, related_name='queue_entry')
    
    # Queue Position
    position = models.IntegerField()
    estimated_wait_time = models.DurationField(null=True, blank=True)
    
    # Timestamps
    entered_at = models.DateTimeField(auto_now_add=True)
    exited_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['position']
        indexes = [
            models.Index(fields=['position']),
        ]
    
    def __str__(self):
        return f"Queue position {self.position} for {self.conversation.conversation_id}"
    
    def exit_queue(self):
        """Remove from queue"""
        self.exited_at = timezone.now()
        self.save(update_fields=['exited_at'])


class ChatBotTraining(models.Model):
    """Training data for AI chatbot"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Training Data
    intent = models.CharField(max_length=100, db_index=True)
    patterns = models.JSONField(default=list, help_text="List of example phrases")
    responses = models.JSONField(default=list, help_text="List of possible responses")
    context = models.CharField(max_length=200, blank=True)
    
    # Metadata
    language = models.CharField(max_length=10, default='en')
    confidence_threshold = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    
    # Usage Statistics
    times_used = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['intent']
        indexes = [
            models.Index(fields=['intent', 'is_active']),
        ]
    
    def __str__(self):
        return f"Training: {self.intent}"
    
    def record_use(self, successful=True):
        """Record usage of this intent"""
        self.times_used += 1
        self.last_used = timezone.now()
        self.success_rate = ((self.success_rate * (self.times_used - 1)) + (1 if successful else 0)) / self.times_used
        self.save(update_fields=['times_used', 'last_used', 'success_rate'])


class ChatFeedback(models.Model):
    """User feedback on chat conversations"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='feedback')
    
    # Feedback
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    
    # Specific Feedback
    resolved_issue = models.BooleanField(default=True)
    agent_helpful = models.BooleanField(default=True)
    response_time_satisfied = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['conversation']
    
    def __str__(self):
        return f"Feedback for {self.conversation.conversation_id}: {self.rating}/5"