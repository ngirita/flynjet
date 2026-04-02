import json
import asyncio
import concurrent.futures
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db import models
from .models import Conversation, Message, ChatQueue, ChatFeedback
import logging

logger = logging.getLogger(__name__)

# Create a thread pool for NLP processing
_nlp_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
_nlp_processor = None
_processor_initialized = False


def init_nlp_processor():
    """Initialize NLP processor in a separate thread"""
    global _nlp_processor, _processor_initialized
    try:
        from .ai.nlp import NLPProcessor
        logger.info("Creating NLP Processor instance...")
        _nlp_processor = NLPProcessor()
        logger.info("NLP Processor instance created, initializing...")
        _nlp_processor.initialize()
        _processor_initialized = True
        logger.info(f"NLP Processor initialized successfully. Is initialized: {_nlp_processor._is_initialized}")
        logger.info(f"Training data count: {len(_nlp_processor.training_data)}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize NLP processor: {e}")
        import traceback
        traceback.print_exc()
        return False


# Initialize once at module load — shared across all requests and consumers
init_nlp_processor()


def process_with_nlp(message_text, conversation_id, user_id):
    """Synchronous function to run NLP processing using the module-level processor."""
    try:
        if not _processor_initialized or _nlp_processor is None:
            logger.error("NLP processor not initialized")
            return None

        user = None
        if user_id:
            from apps.accounts.models import User
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        return _nlp_processor.process_message(message_text, conversation_id, user)
    except Exception as e:
        logger.error(f"Error in process_with_nlp: {e}")
        import traceback
        traceback.print_exc()
        return None


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat"""

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        if not await self.has_permission():
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        history = await self.get_history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': history
        }))

        logger.info(f"Chat connected for conversation {self.conversation_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"Chat disconnected for conversation {self.conversation_id}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'transfer':
                await self.handle_transfer(data)
            elif message_type == 'system_message':
                await self.handle_system_message(data)
            elif message_type == 'switch_to_ai_request':
                await self.handle_switch_to_ai_request(data)

        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_message(self, data):
        """Handle regular text message"""
        message_text = data.get('message', '').strip()
        client_id = data.get('client_id', None)

        if not message_text:
            return

        # Save message to database
        message = await self.save_message(message_text, is_ai=False)

        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(message.id),
                    'sender': message.sender.email if message.sender and hasattr(message.sender, 'email') else 'System',
                    'sender_name': message.sender_name,
                    'message': message.message,
                    'timestamp': message.created_at.isoformat(),
                    'is_agent': message.is_agent,
                    'is_ai': message.is_ai,
                    'client_id': client_id
                }
            }
        )

        # Refresh conversation to get the absolute latest state from DB
        conversation = await self.refresh_conversation()

        # FIXED: AI should respond ONLY when:
        # 1. No human agent is assigned AND
        # 2. No agent is actively viewing the conversation AND
        # 3. The message itself is not from an agent
        should_ai_respond = (
            conversation is not None
            and conversation.agent is None                      # No human agent assigned
            and conversation.active_agent_viewing is None       # No agent viewing
            and not message.is_agent                            # Message not from an agent
        )

        logger.info(
            f"should_ai_respond={should_ai_respond} | "
            f"agent={conversation.agent if conversation else 'N/A'} | "
            f"active_viewing={conversation.active_agent_viewing if conversation else 'N/A'} | "
            f"is_agent={message.is_agent}"
        )

        if should_ai_respond:
            await self.process_ai_response(message_text)

    async def handle_switch_to_ai_request(self, data):
        """Handle user request to switch back to AI"""
        logger.info(f"=== SWITCH TO AI REQUEST START ===")
        conversation = await self.refresh_conversation()

        logger.info(f"Conversation ID: {self.conversation_id}")
        logger.info(f"Conversation agent: {conversation.agent if conversation else 'None'}")
        logger.info(f"Conversation status: {conversation.status if conversation else 'None'}")

        if conversation:
            if conversation.status == 'waiting':
                conversation.status = 'active'
                await database_sync_to_async(conversation.save)(update_fields=['status'])
                logger.info(f"Changed status from waiting to active")

            if conversation.agent:
                conversation.agent = None
                await database_sync_to_async(conversation.save)(update_fields=['agent'])
                logger.info(f"Removed agent")

            # FIXED: Also clear active_agent_viewing
            if conversation.active_agent_viewing:
                conversation.active_agent_viewing = None
                conversation.agent_viewing_since = None
                await database_sync_to_async(conversation.save)(update_fields=['active_agent_viewing', 'agent_viewing_since'])
                logger.info(f"Cleared active_agent_viewing")

            await self.save_system_message("Conversation switched back to AI assistant")

            await self.send(text_data=json.dumps({
                'type': 'switch_to_ai_confirmed',
                'message': 'Switched back to AI assistant'
            }))

            await self.channel_layer.group_send(
                'agents',
                {
                    'type': 'ai_took_over',
                    'conversation_id': self.conversation_id,
                    'message': 'Conversation switched back to AI by user request'
                }
            )

            logger.info(f"Conversation {self.conversation_id} switched back to AI")
        else:
            logger.error(f"Conversation not found: {self.conversation_id}")

    async def handle_system_message(self, data):
        """Handle system messages"""
        message_text = data.get('message', '').strip()
        message = await self.save_system_message(message_text)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(message.id),
                    'sender': 'System',
                    'sender_name': 'System',
                    'message': message.message,
                    'timestamp': message.created_at.isoformat(),
                    'is_agent': True,
                    'is_ai': False
                }
            }
        )

    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        user = self.scope['user']

        user_email = 'Guest'
        if user and user.is_authenticated:
            user_email = user.email

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user': user_email,
                'is_typing': is_typing,
                'sender_channel': self.channel_name
            }
        )

    async def handle_transfer(self, data):
        """Handle transfer to human agent — called only when user explicitly requests one"""
        conversation = await self.get_conversation()
        if conversation:
            await self.transfer_to_agent(conversation)

    async def transfer_to_agent(self, conversation):
        """Transfer conversation to human agent"""
        await self.update_conversation_status(conversation.conversation_id, 'waiting')
        await self.add_to_queue(conversation)

        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'position': await self.get_queue_position(conversation),
            'message': 'Connecting you to a human agent. Please wait...'
        }))

        user_display = await self.get_user_display(conversation)

        await self.channel_layer.group_send(
            'agents',
            {
                'type': 'new_queue_item',
                'data': {
                    'conversation_id': conversation.conversation_id,
                    'user': user_display,
                    'subject': conversation.subject
                }
            }
        )

        transfer_msg = await self.save_system_message(
            "You've been added to the queue. A human agent will be with you shortly."
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(transfer_msg.id),
                    'sender': 'System',
                    'sender_name': 'FlynJet Support',
                    'message': transfer_msg.message,
                    'timestamp': transfer_msg.created_at.isoformat(),
                    'is_agent': True,
                    'is_ai': False
                }
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message']
        }))

    async def typing_indicator(self, event):
        if event.get('sender_channel') == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': event['user'],
            'is_typing': event['is_typing']
        }))

    async def agent_assigned(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': {
                'sender': 'System',
                'sender_name': 'System',
                'message': f"Agent {event['agent_name']} has joined the conversation. You are now chatting with a human agent.",
                'timestamp': timezone.now().isoformat(),
                'is_agent': True,
                'is_ai': False
            }
        }))

    async def switch_to_ai(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': {
                'sender': 'System',
                'sender_name': 'System',
                'message': "The conversation has been switched back to AI assistant. How can I help you?",
                'timestamp': timezone.now().isoformat(),
                'is_agent': True,
                'is_ai': False
            }
        }))

    async def chat_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_ended',
            'message': event.get('message', 'This conversation has been ended.')
        }))

    @database_sync_to_async
    def has_permission(self):
        user = self.scope['user']
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            if user.is_authenticated:
                return (user.is_staff or user == conversation.user or
                        user == conversation.agent or
                        (hasattr(user, 'user_type') and user.user_type in ['admin', 'agent']))
            return True  # Allow guests to connect to their own conversation
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def get_conversation(self):
        try:
            return Conversation.objects.get(conversation_id=self.conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def refresh_conversation(self):
        """Always fetch fresh from DB to get the latest agent/status fields."""
        try:
            return Conversation.objects.get(conversation_id=self.conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def update_conversation_status(self, conversation_id, status):
        try:
            conversation = Conversation.objects.get(conversation_id=conversation_id)
            conversation.status = status
            conversation.save(update_fields=['status'])
            return conversation
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, message_text, is_ai=False):
        conversation = Conversation.objects.get(conversation_id=self.conversation_id)
        user = self.scope['user']

        is_agent = False
        sender_name = 'Guest'

        if user.is_authenticated:
            sender_name = user.get_full_name() or user.email
            if hasattr(user, 'user_type'):
                is_agent = user.user_type in ['admin', 'agent']
            if user.is_staff:
                is_agent = True

        return Message.objects.create(
            conversation=conversation,
            sender=user if user.is_authenticated else None,
            sender_name=sender_name,
            message=message_text,
            is_agent=is_agent,
            is_ai=is_ai
        )

    @database_sync_to_async
    def save_system_message(self, message_text):
        conversation = Conversation.objects.get(conversation_id=self.conversation_id)
        return Message.objects.create(
            conversation=conversation,
            sender=None,
            sender_name='System',
            message=message_text,
            is_agent=True,
            is_ai=False
        )

    @database_sync_to_async
    def save_ai_message(self, message_text, intent, confidence, suggestions):
        conversation = Conversation.objects.get(conversation_id=self.conversation_id)
        return Message.objects.create(
            conversation=conversation,
            sender=None,
            sender_name='FlynJet Assistant',
            message=message_text,
            is_agent=False,
            is_ai=True,
            intent=intent,
            confidence=confidence,
            suggested_responses=suggestions
        )

    @database_sync_to_async
    def get_user_display(self, conversation):
        """Safely fetch user display string in a sync context."""
        if conversation.user_id:
            try:
                from apps.accounts.models import User
                user = User.objects.get(pk=conversation.user_id)
                return user.email
            except Exception:
                pass
        return 'Guest'

    @database_sync_to_async
    def get_history(self):
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            messages = conversation.messages.all().order_by('created_at')[:50]

            history = []
            for msg in messages:
                sender_name = msg.sender_name
                if not sender_name and msg.sender:
                    sender_name = msg.sender.get_full_name() or msg.sender.email
                elif not sender_name:
                    sender_name = 'System'

                history.append({
                    'id': str(msg.id),
                    'sender': msg.sender.email if msg.sender and hasattr(msg.sender, 'email') else 'System',
                    'sender_name': sender_name,
                    'message': msg.message,
                    'timestamp': msg.created_at.isoformat(),
                    'is_agent': msg.is_agent,
                    'is_ai': msg.is_ai,
                    'suggested_responses': msg.suggested_responses if msg.is_ai else []
                })
            return history
        except Conversation.DoesNotExist:
            return []

    @database_sync_to_async
    def get_message_count(self):
        """Get number of messages in conversation"""
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            return conversation.messages.count()
        except Conversation.DoesNotExist:
            return 0

    @database_sync_to_async
    def add_to_queue(self, conversation):
        from .models import ChatQueue
        max_position = ChatQueue.objects.aggregate(models.Max('position'))['position__max'] or 0
        ChatQueue.objects.get_or_create(
            conversation=conversation,
            exited_at__isnull=True,
            defaults={
                'position': max_position + 1,
                'estimated_wait_time': timezone.timedelta(minutes=5)
            }
        )
        conversation.status = 'waiting'
        conversation.save(update_fields=['status'])

    @database_sync_to_async
    def get_queue_position(self, conversation):
        try:
            queue = ChatQueue.objects.get(conversation=conversation, exited_at__isnull=True)
            return queue.position
        except ChatQueue.DoesNotExist:
            return None

    async def process_ai_response(self, message_text):
        """Process message with AI and get response"""
        try:
            logger.info(f"Processing AI response for: {message_text}")

            conversation = await self.get_conversation()
            if not conversation:
                logger.error(f"Conversation not found: {self.conversation_id}")
                return None

            user_id = conversation.user_id

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _nlp_executor,
                process_with_nlp,
                message_text,
                self.conversation_id,
                user_id
            )

            logger.info(f"AI Response received: {response}")

            if response and response.get('response'):
                ai_message = await self.save_ai_message(
                    response['response'],
                    response.get('intent', ''),
                    response.get('confidence', 0.0),
                    response.get('suggestions', [])
                )

                await self.channel_layer.group_send(
                    self.room_group_name,
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
                            'suggestions': response.get('suggestions', [])
                        }
                    }
                )

                if response.get('suggestions'):
                    await self.send(text_data=json.dumps({
                        'type': 'suggestions',
                        'suggestions': response['suggestions']
                    }))

                message_count = await self.get_message_count()
                is_first_message = message_count <= 2

                should_transfer = False

                if not is_first_message and response.get('intent') == 'agent':
                    user_message_lower = message_text.lower().strip()
                    agent_keywords = [
                        'agent', 'human', 'speak to', 'talk to',
                        'customer service', 'live agent', 'real person'
                    ]
                    if any(keyword in user_message_lower for keyword in agent_keywords):
                        should_transfer = True
                        logger.info("User explicitly requested agent transfer")
                    else:
                        logger.info("Intent was 'agent' but no agent keywords found — not transferring")
                else:
                    logger.info(
                        f"Not transferring — is_first_message={is_first_message}, "
                        f"intent={response.get('intent')}"
                    )

                if should_transfer:
                    await self.transfer_to_agent(conversation)

                return ai_message

            else:
                logger.warning(f"No valid AI response for: {message_text}")
                fallback_message = await self.save_ai_message(
                    "I'm here to help! Could you please rephrase your question? "
                    "I can assist with flight bookings, booking status, fleet information, and more. "
                    "You can also say 'talk to agent' if you need human assistance.",
                    'fallback',
                    0.0,
                    ['Book a flight', 'Check status', 'Fleet info', 'Talk to agent']
                )

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': str(fallback_message.id),
                            'sender': 'FlynJet Assistant',
                            'sender_name': 'FlynJet Assistant',
                            'message': fallback_message.message,
                            'timestamp': fallback_message.created_at.isoformat(),
                            'is_agent': False,
                            'is_ai': True,
                            'suggestions': ['Book a flight', 'Check status', 'Fleet info', 'Talk to agent']
                        }
                    }
                )

                return fallback_message

        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            import traceback
            traceback.print_exc()

            error_message = await self.save_ai_message(
                "I'm having a bit of trouble right now. Please try again or click 'Talk to agent' for immediate assistance.",
                'error',
                0.0,
                ['Talk to agent', 'Try again']
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(error_message.id),
                        'sender': 'FlynJet Assistant',
                        'sender_name': 'FlynJet Assistant',
                        'message': error_message.message,
                        'timestamp': error_message.created_at.isoformat(),
                        'is_agent': False,
                        'is_ai': True,
                        'suggestions': ['Talk to agent', 'Try again']
                    }
                }
            )

            return None
        
    async def request_rating(self, event):
        """Send rating request to user"""
        await self.send(text_data=json.dumps({
            'type': 'request_rating',
            'conversation_id': event.get('conversation_id'),
            'message': event.get('message', 'How would you rate your experience?')
        }))


class AgentConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for support agents"""

    async def connect(self):
        self.user = self.scope['user']

        if not await self.is_agent():
            await self.close()
            return

        await self.channel_layer.group_add('agents', self.channel_name)
        await self.accept()
        await self.send_queue()
        logger.info(f"Agent {self.user.email} connected")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('agents', self.channel_name)
        logger.info(f"Agent {self.user.email} disconnected")

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'accept_chat':
            await self.accept_chat(data)
        elif message_type == 'update_status':
            await self.update_status(data)

    async def new_queue_item(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_queue',
            'data': {
                'conversation_id': event.get('data', {}).get('conversation_id'),
                'user': event.get('data', {}).get('user', 'Guest'),
                'subject': event.get('data', {}).get('subject', '')
            }
        }))

    async def queue_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'queue': event.get('queue', [])
        }))

    async def ai_took_over(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ai_took_over',
            'conversation_id': event.get('conversation_id'),
            'message': event.get('message', 'Conversation switched back to AI')
        }))

    @database_sync_to_async
    def is_agent(self):
        return (self.user.is_authenticated and
                (hasattr(self.user, 'user_type') and self.user.user_type in ['agent', 'admin']) or
                self.user.is_staff)

    @database_sync_to_async
    def send_queue(self):
        from .models import ChatQueue

        queue = ChatQueue.objects.select_related('conversation__user').filter(
            exited_at__isnull=True
        ).order_by('position')

        queue_data = []
        for item in queue:
            user_display = 'Guest'
            if item.conversation.user and hasattr(item.conversation.user, 'email'):
                user_display = item.conversation.user.email

            queue_data.append({
                'position': item.position,
                'conversation_id': item.conversation.conversation_id,
                'user': user_display,
                'subject': item.conversation.subject,
                'waiting_time': str(timezone.now() - item.entered_at).split('.')[0]
            })

        asyncio.create_task(self.send(text_data=json.dumps({
            'type': 'queue',
            'queue': queue_data
        })))

    @database_sync_to_async
    def accept_chat(self, data):
        from .models import ChatQueue

        conversation_id = data.get('conversation_id')

        try:
            conversation = Conversation.objects.get(conversation_id=conversation_id)

            conversation.status = 'active'
            conversation.agent = self.user
            conversation.active_agent_viewing = self.user  # FIXED: Also set viewing
            conversation.first_response_at = timezone.now()
            if conversation.started_at:
                conversation.response_time = conversation.first_response_at - conversation.started_at
            conversation.save(update_fields=['status', 'agent', 'active_agent_viewing', 'first_response_at', 'response_time'])

            Message.objects.create(
                conversation=conversation,
                sender=self.user,
                sender_name=f"Agent {self.user.get_full_name() or self.user.email}",
                message=f"Agent {self.user.get_full_name() or self.user.email} has joined the conversation",
                is_agent=True,
                message_type='system'
            )

            ChatQueue.objects.filter(conversation=conversation).update(exited_at=timezone.now())

            asyncio.create_task(self.channel_layer.group_send(
                f'chat_{conversation_id}',
                {
                    'type': 'agent_assigned',
                    'agent_name': self.user.get_full_name() or self.user.email,
                    'agent_id': self.user.id
                }
            ))

        except Conversation.DoesNotExist:
            pass

    @database_sync_to_async
    def update_status(self, data):
        pass