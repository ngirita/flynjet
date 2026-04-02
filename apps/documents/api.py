from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import FileResponse
from .models import GeneratedDocument, DocumentTemplate, DocumentSigning
from .serializers import (
    GeneratedDocumentSerializer, DocumentTemplateSerializer,
    DocumentSigningSerializer
)
from .generators import DocumentGenerator

class DocumentViewSet(viewsets.ModelViewSet):
    """API for documents"""
    serializer_class = GeneratedDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return GeneratedDocument.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download document"""
        document = self.get_object()
        document.record_download()
        
        if document.pdf_file:
            response = FileResponse(document.pdf_file)
            response['Content-Disposition'] = f'attachment; filename="{document.document_number}.pdf"'
            return response
        return Response({'error': 'File not found'}, status=404)
    
    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """Sign document"""
        document = self.get_object()
        
        signing, created = DocumentSigning.objects.get_or_create(
            document=document,
            signer=request.user,
            defaults={
                'signer_email': request.user.email,
                'signer_name': request.user.get_full_name(),
                'expires_at': timezone.now() + timezone.timedelta(days=7)
            }
        )
        
        signature_data = request.data.get('signature')
        if signature_data:
            signing.signature_data = signature_data
            signing.status = 'signed'
            signing.verified_at = timezone.now()
            signing.save()
            
            document.is_signed = True
            document.signed_at = timezone.now()
            document.save()
            
            return Response({'status': 'signed'})
        
        return Response({'error': 'Signature data required'}, status=400)
    
    @action(detail=True, methods=['get'])
    def verify(self, request, pk=None):
        """Verify document authenticity"""
        document = self.get_object()
        return Response({
            'is_valid': document.is_valid(),
            'document_number': document.document_number,
            'created_at': document.created_at,
            'is_signed': document.is_signed,
            'signed_at': document.signed_at
        })


class DocumentTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """API for document templates"""
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = DocumentTemplate.objects.filter(is_active=True)


class DocumentSigningViewSet(viewsets.ReadOnlyModelViewSet):
    """API for document signatures"""
    serializer_class = DocumentSigningSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DocumentSigning.objects.filter(signer=self.request.user)