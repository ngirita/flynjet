#!/usr/bin/env python
import os
import sys
import datetime
import subprocess
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def backup_database():
    """Backup PostgreSQL database"""
    db_name = os.getenv('DB_NAME', 'flynjet_db')
    db_user = os.getenv('DB_USER', 'flynjet_user')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    
    # Create backup filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"backup_{db_name}_{timestamp}.sql"
    
    # Run pg_dump
    try:
        subprocess.run([
            'pg_dump',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-d', db_name,
            '-f', backup_file,
            '-F', 'c'  # Custom format
        ], check=True)
        
        print(f"Database backup created: {backup_file}")
        
        # Compress backup
        subprocess.run(['gzip', backup_file], check=True)
        compressed_file = f"{backup_file}.gz"
        print(f"Backup compressed: {compressed_file}")
        
        return compressed_file
        
    except subprocess.CalledProcessError as e:
        print(f"Backup failed: {e}")
        return None

def upload_to_s3(file_path):
    """Upload backup to S3"""
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('AWS_BACKUP_BUCKET')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not all([aws_access_key, aws_secret_key, bucket_name]):
        print("AWS credentials not configured. Skipping S3 upload.")
        return False
    
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )
        
        # Create S3 key with date folder
        date_folder = datetime.datetime.now().strftime('%Y/%m/%d')
        s3_key = f"database_backups/{date_folder}/{os.path.basename(file_path)}"
        
        s3.upload_file(file_path, bucket_name, s3_key)
        print(f"Backup uploaded to s3://{bucket_name}/{s3_key}")
        
        return True
        
    except Exception as e:
        print(f"S3 upload failed: {e}")
        return False

def cleanup_old_backups(days=7):
    """Delete backups older than specified days"""
    import glob
    import os
    from datetime import datetime, timedelta
    
    backup_files = glob.glob("backup_*.sql.gz")
    cutoff_date = datetime.now() - timedelta(days=days)
    
    for file in backup_files:
        # Extract date from filename (backup_dbname_YYYYMMDD_HHMMSS.sql.gz)
        try:
            date_str = file.split('_')[2]
            file_date = datetime.strptime(date_str, '%Y%m%d')
            
            if file_date < cutoff_date:
                os.remove(file)
                print(f"Deleted old backup: {file}")
        except (IndexError, ValueError):
            # Skip files that don't match the pattern
            continue

def main():
    print("Starting database backup...")
    
    # Create backup
    backup_file = backup_database()
    
    if backup_file:
        # Upload to S3
        upload_to_s3(backup_file)
        
        # Cleanup old backups
        cleanup_old_backups()
        
        print("Backup process completed!")
    else:
        print("Backup failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()