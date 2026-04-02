#!/usr/bin/env python
import os
import sys
import subprocess
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def restore_database(backup_file):
    """Restore PostgreSQL database from backup"""
    db_name = os.getenv('DB_NAME', 'flynjet_db')
    db_user = os.getenv('DB_USER', 'flynjet_user')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    
    if not backup_file:
        print("Please specify backup file to restore")
        return False
    
    if not os.path.exists(backup_file):
        print(f"Backup file not found: {backup_file}")
        return False
    
    # Decompress if needed
    if backup_file.endswith('.gz'):
        import gzip
        import shutil
        
        decompressed = backup_file[:-3]
        with gzip.open(backup_file, 'rb') as f_in:
            with open(decompressed, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        backup_file = decompressed
    
    # Restore database
    try:
        # Drop connections
        subprocess.run([
            'psql',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-d', 'postgres',
            '-c', f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}';"
        ], check=True)
        
        # Drop and recreate database
        subprocess.run([
            'dropdb',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '--if-exists',
            db_name
        ], check=True)
        
        subprocess.run([
            'createdb',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            db_name
        ], check=True)
        
        # Restore from backup
        subprocess.run([
            'pg_restore',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-d', db_name,
            '-c',
            backup_file
        ], check=True)
        
        print(f"Database restored from: {backup_file}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Restore failed: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python restore_db.py <backup_file>")
        sys.exit(1)
    
    backup_file = sys.argv[1]
    success = restore_database(backup_file)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()