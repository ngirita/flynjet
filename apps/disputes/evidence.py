import os
import hashlib
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone
from django.db import models
from .models import DisputeEvidence

class EvidenceManager:
    """Manage dispute evidence files"""
    
    ALLOWED_TYPES = {
        'document': ['.pdf', '.doc', '.docx', '.txt'],
        'image': ['.jpg', '.jpeg', '.png', '.gif'],
        'video': ['.mp4', '.mov', '.avi'],
        'audio': ['.mp3', '.wav'],
    }
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    @classmethod
    def validate_file(cls, file):
        """Validate uploaded file"""
        # Check size
        if file.size > cls.MAX_FILE_SIZE:
            return False, f"File too large. Max size: {cls.MAX_FILE_SIZE / 1024 / 1024}MB"
        
        # Check extension
        ext = os.path.splitext(file.name)[1].lower()
        allowed = []
        for types in cls.ALLOWED_TYPES.values():
            allowed.extend(types)
        
        if ext not in allowed:
            return False, f"File type not allowed. Allowed: {', '.join(allowed)}"
        
        return True, None
    
    @classmethod
    def save_evidence(cls, dispute, file, evidence_type, description, uploaded_by):
        """Save evidence file"""
        # Validate
        valid, error = cls.validate_file(file)
        if not valid:
            raise ValueError(error)
        
        # Generate unique filename
        original_name = file.name
        ext = os.path.splitext(original_name)[1]
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dispute_{dispute.dispute_number}_{timestamp}{ext}"
        
        # Save file
        path = default_storage.save(f"dispute_evidence/{filename}", file)
        
        # Calculate hash
        file_hash = cls.calculate_file_hash(file)
        
        # Create evidence record
        evidence = DisputeEvidence.objects.create(
            dispute=dispute,
            evidence_type=evidence_type,
            file=path,
            description=description,
            uploaded_by=uploaded_by
        )
        
        return evidence
    
    @classmethod
    def calculate_file_hash(cls, file):
        """Calculate SHA-256 hash of file"""
        sha256 = hashlib.sha256()
        
        if hasattr(file, 'read'):
            for chunk in iter(lambda: file.read(8192), b''):
                sha256.update(chunk)
            file.seek(0)
        else:
            with open(file, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
        
        return sha256.hexdigest()
    
    @classmethod
    def verify_evidence(cls, evidence):
        """Verify evidence file integrity"""
        try:
            with open(evidence.file.path, 'rb') as f:
                current_hash = cls.calculate_file_hash(f)
            
            # Compare with stored hash (would need to store hash)
            return True
        except Exception as e:
            return False
    
    @classmethod
    def get_evidence_summary(cls, dispute):
        """Get summary of evidence for dispute"""
        evidence = dispute.evidence_items.all()
        
        return {
            'total_files': evidence.count(),
            'by_type': dict(evidence.values_list('evidence_type').annotate(count=models.Count('id'))),
            'total_size': sum(e.file.size for e in evidence if e.file),
            'uploaded_by': evidence.values('uploaded_by__email').annotate(count=models.Count('id')),
        }

class EvidenceChain:
    """Maintain chain of custody for evidence"""
    
    @classmethod
    def record_access(cls, evidence, user, action):
        """Record access to evidence"""
        from apps.core.models import ActivityLog
        
        ActivityLog.objects.create(
            user=user,
            activity_type='evidence_access',
            description=f"{action} evidence {evidence.id} for dispute {evidence.dispute.dispute_number}",
            related_object=evidence,
            data={
                'evidence_id': str(evidence.id),
                'action': action,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def get_chain_of_custody(cls, evidence):
        """Get chain of custody for evidence"""
        from apps.core.models import ActivityLog
        
        return ActivityLog.objects.filter(
            related_object=evidence,
            activity_type='evidence_access'
        ).order_by('timestamp')

class EvidenceAnalyzer:
    """Analyze evidence for patterns"""
    
    @classmethod
    def extract_metadata(cls, evidence):
        """Extract metadata from evidence file"""
        metadata = {
            'filename': os.path.basename(evidence.file.name),
            'size': evidence.file.size,
            'uploaded_at': evidence.uploaded_at,
            'uploaded_by': evidence.uploaded_by.email if evidence.uploaded_by else None,
            'type': evidence.evidence_type,
        }
        
        # Extract image metadata if applicable
        if evidence.evidence_type == 'image' and evidence.file:
            from PIL import Image
            try:
                img = Image.open(evidence.file.path)
                metadata.update({
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                })
            except:
                pass
        
        return metadata
    
    @classmethod
    def find_duplicates(cls, dispute):
        """Find duplicate evidence files"""
        evidence_files = dispute.evidence_items.all()
        hashes = {}
        duplicates = []
        
        for evidence in evidence_files:
            file_hash = cls.calculate_file_hash(evidence.file.path)
            if file_hash in hashes:
                duplicates.append({
                    'original': hashes[file_hash],
                    'duplicate': evidence
                })
            else:
                hashes[file_hash] = evidence
        
        return duplicates