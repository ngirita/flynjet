from rest_framework import serializers
from .models import GeneratedDocument, DocumentTemplate, DocumentSigning

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = ['id', 'name', 'document_type', 'version', 'is_active']


class GeneratedDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    verify_url = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedDocument
        fields = [
            'id', 'document_number', 'document_type', 'title',
            'created_at', 'status', 'is_signed', 'download_url',
            'verify_url', 'view_count', 'download_count'
        ]
    
    def get_download_url(self, obj):
        return f"/api/v1/documents/{obj.id}/download/"
    
    def get_verify_url(self, obj):
        return f"/documents/verify/{obj.access_token}/"


class DocumentSigningSerializer(serializers.ModelSerializer):
    document_info = GeneratedDocumentSerializer(source='document', read_only=True)
    
    class Meta:
        model = DocumentSigning
        fields = '__all__'