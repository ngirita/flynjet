from django.contrib import admin
from .models import DocumentTemplate, GeneratedDocument, DocumentSigning, DocumentArchive

@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'document_type', 'version', 'is_active', 'created_at']
    list_filter = ['document_type', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Template Info', {
            'fields': ('name', 'document_type', 'description', 'is_active')
        }),
        ('File', {
            'fields': ('template_file',)
        }),
        ('Configuration', {
            'fields': ('variables', 'styles')
        }),
        ('Version Control', {
            'fields': ('version', 'previous_version')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ['document_number', 'user', 'document_type', 'status', 'created_at', 'is_signed']
    list_filter = ['document_type', 'status', 'is_signed', 'created_at']
    search_fields = ['document_number', 'user__email', 'title']
    readonly_fields = ['document_number', 'access_token', 'created_at', 'updated_at', 
                       'viewed_at', 'downloaded_at', 'view_count', 'download_count']
    
    fieldsets = (
        ('Document Info', {
            'fields': ('document_number', 'user', 'booking', 'invoice', 'template')
        }),
        ('Content', {
            'fields': ('document_type', 'title', 'description', 'content_data')
        }),
        ('Files', {
            'fields': ('pdf_file', 'html_file', 'file_size')
        }),
        ('Status', {
            'fields': ('status', 'is_signed', 'signed_at')
        }),
        ('Security', {
            'fields': ('access_token', 'access_password', 'expires_at')
        }),
        ('Tracking', {
            'fields': ('viewed_at', 'downloaded_at', 'view_count', 'download_count')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(DocumentSigning)
class DocumentSigningAdmin(admin.ModelAdmin):
    list_display = ['document', 'signer_email', 'signing_method', 'status', 'created_at']
    list_filter = ['signing_method', 'status']
    search_fields = ['document__document_number', 'signer_email', 'signer_name']
    readonly_fields = ['created_at', 'verified_at', 'signature_hash']
    
    fieldsets = (
        ('Document', {
            'fields': ('document',)
        }),
        ('Signer', {
            'fields': ('signer', 'signer_email', 'signer_name')
        }),
        ('Signing Details', {
            'fields': ('signing_method', 'status', 'signature_data', 'signature_hash')
        }),
        ('Verification', {
            'fields': ('verification_code', 'verification_sent_at', 'verified_at')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'location', 'user_agent', 'expires_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(DocumentArchive)
class DocumentArchiveAdmin(admin.ModelAdmin):
    list_display = ['archive_reference', 'original_document', 'archive_date', 'retention_until']
    list_filter = ['archive_date']
    search_fields = ['archive_reference', 'original_document__document_number']
    readonly_fields = ['archive_date', 'file_hash']
    
    fieldsets = (
        ('Archive Info', {
            'fields': ('archive_reference', 'original_document', 'archive_reason')
        }),
        ('File', {
            'fields': ('archived_file', 'file_hash', 'file_size')
        }),
        ('Retention', {
            'fields': ('retention_until', 'is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('archive_date',),
            'classes': ('collapse',)
        }),
    )