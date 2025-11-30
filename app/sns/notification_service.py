# This module provides a high-level notification service that combines SNS and SQS
# It handles sending notifications and queuing messages for async processing
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from .sns_client import SNSClient
from ..sqs.sqs_client import SQSClient
from ..cognito_client import CognitoClient

load_dotenv()

# This service orchestrates notifications across SNS topics and SQS queues
class NotificationService:
    
    def __init__(self):
        self.sns_client = SNSClient()
        self.sqs_client = SQSClient()
        self.cognito_client = CognitoClient()
    
    # This sends notifications via SNS and queues them in SQS for processing
    # It auto-subscribes recipients if not provided, then publishes the message
    def send_notification(
        self,
        topic_name: str,
        queue_name: str,
        subject: str,
        data: Dict[str, Any],
        recipients: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        try:
            # Get or create resources
            topic_arn = self.sns_client.create_topic(topic_name)
            queue_url = self.sqs_client.create_queue(queue_name)  # Returns URL but we need name for send_message
            
            # Auto-subscribe recipients
            if recipients is None:
                recipients = self._get_all_users()
            subscriptions = self._subscribe_all(topic_arn, recipients)
            
            # Build message
            message = self._format_message(subject, data)
            
            # Publish to SNS
            sns_success = self.sns_client.publish_message(topic_arn, subject, message)
            
            # Queue in SQS (using queue_name, not URL)
            sqs_success = self.sqs_client.send_message(
                queue_name,  # send_message needs name, not URL
                {'message': message, 'subject': subject},
                0
            )
            
            return {
                'success': True,
                'sns_published': sns_success,
                'sqs_queued': sqs_success,
                'subscriptions': len(subscriptions),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_all_users(self) -> List[Dict[str, str]]:
        try:
            users = self.cognito_client.list_all_users()
            contacts = []
            for user in users:
                if email := user.get('email'):
                    contacts.append({'email': email})
                if phone := user.get('phone_number'):
                    contacts.append({'phone': phone})
            return contacts
        except:
            return []
    
    def _subscribe_all(self, topic_arn: str, recipients: List[Dict[str, str]]) -> List[str]:
        successful = []
        for recipient in recipients:
            try:
                if 'email' in recipient:
                    if self.sns_client.subscribe_email(topic_arn, recipient['email']):
                        successful.append(recipient['email'])
                elif 'phone' in recipient:
                    if self.sns_client.subscribe_sms(topic_arn, recipient['phone']):
                        successful.append(recipient['phone'])
            except:
                pass
        return successful
    
    def _format_message(self, subject: str, data: Dict[str, Any]) -> str:
        lines = [f"Event: {subject}", ""]
        for key, value in data.items():
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines)


# Global instance - reuse across app
_notification_service = None

def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
