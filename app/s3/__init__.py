"""
S3 module for handling bulk data operations
Provides file upload, download, and management without database storage
"""

from .s3_client import S3Client
from .service import BulkDataService

__all__ = ['S3Client', 'BulkDataService']