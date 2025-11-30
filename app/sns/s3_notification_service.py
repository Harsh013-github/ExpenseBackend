import os
import boto3
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from .sns_client import SNSClient
from ..sqs.sqs_client import SQSClient

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV, override=True)


class S3UploadNotificationService:
    
    def __init__(self):
        self.sns_client = SNSClient()
        self.sqs_client = SQSClient()
        self.enabled = os.getenv('SNS_ENABLE_NOTIFICATIONS', 'true').lower() == 'true'
        
        # Topic and queue names
        self.topic_name = os.getenv('SNS_S3_UPLOAD_TOPIC', 's3-file-upload-notifications')
        self.queue_name = os.getenv('SQS_S3_UPLOAD_QUEUE', 's3-upload-notification-queue')
        
        # Initialize Cognito client to get all users
        self.cognito_client = boto3.client(
            'cognito-idp',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_COGNITO_REGION', 'us-east-1')
        )
        self.user_pool_id = os.getenv('AWS_COGNITO_USER_POOL_ID')
        
        # Get or create topic ARN
        self.topic_arn = None
        if self.enabled:
            self.topic_arn = self.sns_client.create_topic(self.topic_name)
    
    def get_all_users_contact_info(self) -> Dict[str, List[str]]:
        try:
            emails = []
            phone_numbers = []
            
            paginator = self.cognito_client.get_paginator('list_users')
            
            for page in paginator.paginate(UserPoolId=self.user_pool_id):
                for user in page.get('Users', []):
                    user_email = None
                    user_phone = None
                    
                    # Extract email and phone from user attributes
                    for attr in user.get('Attributes', []):
                        if attr['Name'] == 'email':
                            user_email = attr['Value']
                        elif attr['Name'] == 'phone_number':
                            user_phone = attr['Value']
                    
                    if user_email:
                        emails.append(user_email)
                    if user_phone:
                        phone_numbers.append(user_phone)
            
            return {
                'emails': emails,
                'phone_numbers': phone_numbers
            }
            
        except Exception as e:
            return {'emails': [], 'phone_numbers': []}
    
    def notify_file_uploaded(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled or not self.topic_arn:
            return {
                'success': False,
                'error': 'Notifications not enabled or topic not found'
            }
        
        try:
            # Get all users' contact information
            contact_info = self.get_all_users_contact_info()
            emails = contact_info.get('emails', [])
            phone_numbers = contact_info.get('phone_numbers', [])
            
            # Format file size for display
            size_mb = file_data.get('size_bytes', 0) / (1024 * 1024)
            size_display = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{file_data.get('size_bytes', 0)} bytes"
            
            # Create notification message
            subject = f"📎 New File Uploaded: {file_data.get('original_filename', 'Unknown')}"
            
            message = f"""
📁 NEW FILE UPLOADED TO S3 BUCKET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📎 File Details:
• Filename: {file_data.get('original_filename', 'N/A')}
• File Key: {file_data.get('file_key', 'N/A')}
• Size: {size_display}
• Uploaded: {file_data.get('uploaded_at', 'N/A')}
• Uploaded By: {file_data.get('uploaded_by', 'System')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated notification from Finance Tracker.
A new file has been uploaded to your shared S3 bucket.

Bucket: {os.getenv('AWS_S3_BUCKET_NAME', 'finance-expenses-bucket')}
Region: {os.getenv('AWS_S3_REGION', 'us-east-1')}
"""
            
            # SMS message (shorter version)
            sms_message = f"📎 New file uploaded: {file_data.get('original_filename', 'Unknown')} ({size_display}) by {file_data.get('uploaded_by', 'System')}"
            
            # Publish to SNS topic with all users subscribed
            sns_result = self.sns_client.publish_to_all_users(
                topic_arn=self.topic_arn,
                subject=subject,
                message=message,
                emails=emails,
                phone_numbers=phone_numbers
            )
            
            # Queue message in SQS for processing
            queue_message = {
                'notification_type': 's3_file_upload',
                'timestamp': datetime.now().isoformat(),
                'file_data': file_data,
                'notification_sent': sns_result.get('message_published', False),
                'emails_notified': len(emails),
                'sms_notified': len(phone_numbers)
            }
            
            sqs_success = self.sqs_client.send_message(
                queue_name=self.queue_name,
                message_body=queue_message
            )
            
            return {
                'success': True,
                'sns_result': sns_result,
                'sqs_queued': sqs_success,
                'users_notified': {
                    'emails': len(emails),
                    'sms': len(phone_numbers)
                },
                'message': f"Notification sent to {len(emails)} email(s) and {len(phone_numbers)} phone(s)"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_notification_stats(self) -> Dict[str, Any]:
        try:
            contact_info = self.get_all_users_contact_info()
            
            subscriptions = []
            if self.topic_arn:
                subscriptions = self.sns_client.list_subscriptions(self.topic_arn)
            
            return {
                'enabled': self.enabled,
                'topic_name': self.topic_name,
                'topic_arn': self.topic_arn,
                'queue_name': self.queue_name,
                'total_users': len(contact_info.get('emails', [])),
                'total_phone_numbers': len(contact_info.get('phone_numbers', [])),
                'total_subscriptions': len(subscriptions),
                'subscription_types': {
                    'email': len([s for s in subscriptions if s.get('Protocol') == 'email']),
                    'sms': len([s for s in subscriptions if s.get('Protocol') == 'sms'])
                }
            }
            
        except Exception as e:
            return {
                'enabled': self.enabled,
                'error': str(e)
            }
