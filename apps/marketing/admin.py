from django.contrib import admin
from .models import Campaign, LoyaltyProgram, LoyaltyAccount, LoyaltyTransaction, Referral, Promotion, PromotionUsage

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_number', 'campaign_type', 'status', 'start_date', 'end_date']
    list_filter = ['campaign_type', 'status', 'start_date']
    search_fields = ['name', 'campaign_number', 'subject']
    readonly_fields = ['campaign_number', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Campaign Info', {
            'fields': ('campaign_number', 'name', 'campaign_type', 'status')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date')
        }),
        ('Targeting', {
            'fields': ('target_audience', 'segment_size')
        }),
        ('Content', {
            'fields': ('subject', 'content', 'template', 'images', 'attachments')
        }),
        ('Budget', {
            'fields': ('budget', 'currency')
        }),
        ('Performance', {
            'fields': ('sent_count', 'delivered_count', 'opened_count', 'clicked_count', 'converted_count', 'revenue_generated')
        }),
        ('A/B Testing', {
            'fields': ('is_ab_test', 'variant_a', 'variant_b', 'winning_variant'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['launch_campaigns', 'pause_campaigns', 'duplicate_campaigns']
    
    def launch_campaigns(self, request, queryset):
        for campaign in queryset:
            campaign.launch()
        self.message_user(request, f"{queryset.count()} campaigns launched.")
    launch_campaigns.short_description = "Launch selected campaigns"
    
    def pause_campaigns(self, request, queryset):
        for campaign in queryset:
            campaign.pause()
        self.message_user(request, f"{queryset.count()} campaigns paused.")
    pause_campaigns.short_description = "Pause selected campaigns"
    
    def duplicate_campaigns(self, request, queryset):
        for campaign in queryset:
            campaign.pk = None
            campaign.campaign_number = None
            campaign.name = f"Copy of {campaign.name}"
            campaign.status = 'draft'
            campaign.save()
        self.message_user(request, f"{queryset.count()} campaigns duplicated.")
    duplicate_campaigns.short_description = "Duplicate selected campaigns"

@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'program_type', 'is_active', 'started_at', 'ended_at']
    list_filter = ['program_type', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Program Info', {
            'fields': ('name', 'program_type', 'is_active')
        }),
        ('Points Configuration', {
            'fields': ('points_per_dollar', 'minimum_points_redemption')
        }),
        ('Tiers', {
            'fields': ('tiers',)
        }),
        ('Benefits', {
            'fields': ('benefits',)
        }),
        ('Rules', {
            'fields': ('enrollment_rules', 'earning_rules', 'redemption_rules')
        }),
        ('Schedule', {
            'fields': ('started_at', 'ended_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_number', 'current_tier', 'points_balance', 'lifetime_points', 'is_active']
    list_filter = ['current_tier', 'is_active']
    search_fields = ['user__email', 'account_number']
    readonly_fields = ['account_number', 'enrolled_at', 'last_activity']
    
    fieldsets = (
        ('Account Info', {
            'fields': ('user', 'account_number', 'program', 'is_active')
        }),
        ('Points', {
            'fields': ('points_balance', 'lifetime_points')
        }),
        ('Tier', {
            'fields': ('current_tier', 'tier_progress')
        }),
        ('Timestamps', {
            'fields': ('enrolled_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['add_points', 'reset_account']
    
    def add_points(self, request, queryset):
        for account in queryset:
            account.add_points(1000, 'admin', 'Manual addition')
        self.message_user(request, f"Added 1000 points to {queryset.count()} accounts.")
    add_points.short_description = "Add 1000 points"
    
    def reset_account(self, request, queryset):
        queryset.update(points_balance=0, lifetime_points=0, current_tier='bronze')
        self.message_user(request, f"Reset {queryset.count()} accounts.")
    reset_account.short_description = "Reset points to zero"

@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ['account', 'transaction_type', 'points', 'source', 'created_at']
    list_filter = ['transaction_type', 'source', 'created_at']
    search_fields = ['account__user__email', 'description']
    readonly_fields = ['created_at']

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referred_email', 'referred_user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['referrer__email', 'referred_email']
    readonly_fields = ['referral_code', 'created_at']
    
    fieldsets = (
        ('Referral Info', {
            'fields': ('referrer', 'referred_email', 'referred_user', 'referral_code')
        }),
        ('Status', {
            'fields': ('status', 'clicked_at', 'signed_up_at', 'first_booking_at')
        }),
        ('Rewards', {
            'fields': ('referrer_reward', 'referred_reward', 'reward_issued_at')
        }),
        ('Timestamps', {
            'fields': ('expires_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['send_reminders']
    
    def send_reminders(self, request, queryset):
        for referral in queryset.filter(status='pending'):
            # Send reminder email
            from django.core.mail import send_mail
            send_mail(
                "Don't forget your friend's referral!",
                f"Remind {referral.referred_email} to sign up using your referral link.",
                'info@flynjet.com',
                [referral.referrer.email],
                fail_silently=False,
            )
        self.message_user(request, f"Reminders sent for {queryset.count()} referrals.")
    send_reminders.short_description = "Send reminder emails"

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['name', 'promotion_code', 'promotion_type', 'is_active', 'start_date', 'end_date']
    list_filter = ['promotion_type', 'is_active']
    search_fields = ['name', 'promotion_code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Promotion Info', {
            'fields': ('name', 'promotion_code', 'description', 'promotion_type')
        }),
        ('Value', {
            'fields': ('discount_percentage', 'discount_amount', 'points_multiplier', 'bonus_points')
        }),
        ('Eligibility', {
            'fields': ('min_booking_amount', 'min_passengers', 'applicable_aircraft', 'applicable_routes', 'user_segments')
        }),
        ('Usage', {
            'fields': ('max_uses_total', 'max_uses_per_user', 'current_uses')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_promotions', 'deactivate_promotions']
    
    def activate_promotions(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} promotions activated.")
    activate_promotions.short_description = "Activate selected promotions"
    
    def deactivate_promotions(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} promotions deactivated.")
    deactivate_promotions.short_description = "Deactivate selected promotions"

@admin.register(PromotionUsage)
class PromotionUsageAdmin(admin.ModelAdmin):
    list_display = ['promotion', 'user', 'booking', 'used_at']
    list_filter = ['used_at']
    search_fields = ['promotion__name', 'user__email', 'booking__booking_reference']
    readonly_fields = ['used_at']