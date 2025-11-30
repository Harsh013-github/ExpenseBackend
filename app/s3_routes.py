# This module handles file upload and management using AWS S3
# It supports receipt images and expense attachments with validation
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status
from fastapi.responses import Response, StreamingResponse
from typing import List
from io import BytesIO
from datetime import datetime
from .auth import get_current_user
from .utils import ok, bad
from .s3.service import BulkDataService

router = APIRouter(prefix="/s3", tags=["S3 Files"])

# This initializes the S3 file service for uploading and retrieving files
try:
    file_service = BulkDataService()
except Exception as e:
    file_service = None

# Import notification service for sending upload notifications
from .sns import get_notification_service

# This endpoint provides information about supported file types and limits
@router.get("/")
def get_s3_info(current=Depends(get_current_user)):
    if not file_service:
        return bad(503, "SERVICE_UNAVAILABLE", "S3 service not configured")
    
    return ok("S3 file service information", {
        "supported_file_types": file_service.get_supported_file_types(),
        "note": "Upload receipts and attachments for expense tracking",
        "max_file_size": "100MB (recommended)"
    })

# This endpoint handles file uploads to S3 with validation and notification
# It checks file type, size, and sends notifications upon successful upload
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current=Depends(get_current_user)
):
    if not file_service:
        return bad(503, "SERVICE_UNAVAILABLE", "S3 service not configured")
    
    try:
        # Validate file
        if not file.filename:
            return bad(400, "INVALID_FILE", "No filename provided")
        
        if not file_service.validate_file_type(file.filename):
            supported = ", ".join(file_service.get_supported_file_types())
            return bad(400, "INVALID_FILE_TYPE", f"File type not supported. Allowed: {supported}")
        
        # Read file content
        file_content = await file.read()
        if len(file_content) == 0:
            return bad(400, "EMPTY_FILE", "File is empty")
        
        # Upload to S3
        result = file_service.upload_bulk_file(file_content, file.filename)
        
        if not result or not result.get('success'):
            error_msg = result.get('error', 'Unknown upload error') if result else 'Upload service failed'
            return bad(500, "UPLOAD_FAILED", error_msg)
        
        # Send notifications using generic notification service
        notification_result = None
        try:
            notif_svc = get_notification_service()
            user_email = current.get('email', 'Unknown user')
            
            notification_result = notif_svc.send_notification(
                topic_name='s3-file-upload-notifications',
                queue_name='s3-upload-notification-queue',
                subject='New File Uploaded',
                data={
                    'file_name': result['original_filename'],
                    'file_key': result['file_key'],
                    'file_size': f"{result['size_bytes']} bytes",
                    'uploaded_by': user_email,
                    'uploaded_at': result['uploaded_at']
                }
            )
        except Exception as e:
            notification_result = {'success': False, 'error': str(e)}
        
        response_data = {
            "file_key": result['file_key'],
            "original_filename": result['original_filename'],
            "size_bytes": result['size_bytes'],
            "uploaded_at": result['uploaded_at']
        }
        
        # Add notification info if available
        if notification_result:
            response_data['notifications'] = notification_result
        
        return ok("File uploaded successfully", response_data)
        
    except Exception as e:
        return bad(500, "UPLOAD_ERROR", "Failed to upload file", str(e))

# This endpoint retrieves a list of all uploaded files from S3 with metadata
@router.get("/files")
def list_files(current=Depends(get_current_user)):
    if not file_service:
        return bad(503, "SERVICE_UNAVAILABLE", "S3 service not configured")
    
    try:
        files = file_service.list_files()
        
        return ok("Files retrieved successfully", {
            "files": files,
            "total_count": len(files)
        })
        
    except Exception as e:
        return bad(500, "LIST_ERROR", "Failed to list files", str(e))
