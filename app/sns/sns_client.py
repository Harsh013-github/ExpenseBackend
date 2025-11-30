# This module handles AWS SNS (Simple Notification Service) operations
# It sends notifications via email and SMS to subscribed users
import os
import boto3
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# This class provides methods to create topics, subscribe users, and publish messages
class SNSClient:
    
    def __init__(self):
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region = os.getenv('AWS_SNS_REGION', 'us-east-1')
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS credentials not found in environment variables")
        
        self.sns_client = boto3.client(
            'sns',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )
    
    # This creates or retrieves an SNS topic for sending notifications
    def create_topic(self, topic_name: str) -> Optional[str]:
        try:
            response = self.sns_client.create_topic(Name=topic_name)
            return response['TopicArn']
        except ClientError as e:
            return None
    
    # This subscribes an email address to receive notifications from a topic
    # Users must confirm their subscription via the email they receive
    def subscribe_email(self, topic_arn: str, email: str) -> bool:
        try:
            subscriptions = self.list_subscriptions(topic_arn)
            existing_emails = [sub['Endpoint'] for sub in subscriptions 
                             if sub['Protocol'] == 'email']
            
            if email in existing_emails:
                return True
            
            self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            return True
            
        except ClientError as e:
            return False
    
    # This subscribes a phone number to receive SMS notifications from a topic
    def subscribe_sms(self, topic_arn: str, phone_number: str) -> bool:
        try:
            subscriptions = self.list_subscriptions(topic_arn)
            existing_phones = [sub['Endpoint'] for sub in subscriptions 
                             if sub['Protocol'] == 'sms']
            
            if phone_number in existing_phones:
                return True
            
            self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol='sms',
                Endpoint=phone_number
            )
            return True
            
        except ClientError as e:
            return False
    
    def list_subscriptions(self, topic_arn: str) -> List[Dict[str, Any]]:
        try:
            response = self.sns_client.list_subscriptions_by_topic(
                TopicArn=topic_arn
            )
            return response.get('Subscriptions', [])
        except ClientError as e:
            return []
    
    # This publishes a message to all subscribers of a topic
    # All subscribed emails and phones receive the notification
    def publish_message(self, topic_arn: str, subject: str, message: str) -> bool:
        try:
            self.sns_client.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=message
            )
            return True
        except ClientError as e:
            return False
    
    def publish_to_all_users(self, topic_arn: str, subject: str, message: str, 
                           emails: List[str] = None, phone_numbers: List[str] = None) -> Dict[str, Any]:
        try:
            results = {
                'email_subscriptions': 0,
                'sms_subscriptions': 0,
                'message_published': False,
                'errors': []
            }
            
            if emails:
                for email in emails:
                    if self.subscribe_email(topic_arn, email):
                        results['email_subscriptions'] += 1
                    else:
                        results['errors'].append(f"Failed to subscribe {email}")
            
            if phone_numbers:
                for phone in phone_numbers:
                    if self.subscribe_sms(topic_arn, phone):
                        results['sms_subscriptions'] += 1
                    else:
                        results['errors'].append(f"Failed to subscribe {phone}")
            
            if self.publish_message(topic_arn, subject, message):
                results['message_published'] = True
            else:
                results['errors'].append("Failed to publish message")
            
            return results
            
        except Exception as e:
            return {
                'email_subscriptions': 0,
                'sms_subscriptions': 0,
                'message_published': False,
                'errors': [str(e)]
            }
    
    def delete_topic(self, topic_arn: str) -> bool:
        try:
            self.sns_client.delete_topic(TopicArn=topic_arn)
            return True
        except ClientError as e:
            return False
