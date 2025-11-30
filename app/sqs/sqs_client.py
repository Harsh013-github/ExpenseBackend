# It manages message queues for asynchronous task processing
import os
import json
import boto3
from typing import Dict, List, Optional, Any
from datetime import datetime
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# This class provides methods to create queues, send/receive messages, and manage queue lifecycle
class SQSClient:
    
    def __init__(self):
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region = os.getenv('AWS_SQS_REGION', 'us-east-1')
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS credentials not found in environment variables")
        
        self.sqs_client = boto3.client(
            'sqs',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )
        
        # Get account ID for ARN construction
        try:
            sts_client = boto3.client(
                'sts',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region
            )
            self.account_id = sts_client.get_caller_identity()['Account']
        except Exception as e:
            self.account_id = None
    
    # This creates a new SQS queue with specified configuration
    # Includes dead-letter queue support for failed message handling
    def create_queue(self, queue_name: str, visibility_timeout: int = 30,
                    message_retention_period: int = 345600,
                    dead_letter_queue_arn: Optional[str] = None,
                    max_receive_count: int = 3) -> Optional[str]:
        try:
            attributes = {
                'VisibilityTimeout': str(visibility_timeout),
                'MessageRetentionPeriod': str(message_retention_period)
            }
            
            # Add dead-letter queue configuration if provided
            if dead_letter_queue_arn:
                redrive_policy = {
                    'deadLetterTargetArn': dead_letter_queue_arn,
                    'maxReceiveCount': str(max_receive_count)
                }
                attributes['RedrivePolicy'] = json.dumps(redrive_policy)
            
            response = self.sqs_client.create_queue(
                QueueName=queue_name,
                Attributes=attributes
            )
            return response['QueueUrl']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'QueueAlreadyExists':
                try:
                    response = self.sqs_client.get_queue_url(QueueName=queue_name)
                    return response['QueueUrl']
                except Exception:
                    pass
            return None
    
    def get_queue_url(self, queue_name: str) -> Optional[str]:
        try:
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            return response['QueueUrl']
        except ClientError as e:
            return None
    
    def get_queue_arn(self, queue_name: str) -> Optional[str]:
        try:
            queue_url = self.get_queue_url(queue_name)
            if not queue_url:
                return None
            
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['QueueArn']
            )
            return response['Attributes'].get('QueueArn')
            
        except ClientError as e:
            return None
    
    # This sends a message to the specified queue for async processing
    # Messages are JSON-encoded and can be delayed for later delivery
    def send_message(self, queue_name: str, message_body: Dict[str, Any],
                    delay_seconds: int = 0) -> bool:
        try:
            queue_url = self.get_queue_url(queue_name)
            if not queue_url:
                return False
            
            self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                DelaySeconds=delay_seconds
            )
            return True
            
        except ClientError as e:
            return False
    
    # This retrieves messages from the queue for processing
    # Supports long polling to reduce empty responses and costs
    def receive_messages(self, queue_name: str, max_messages: int = 1,
                        wait_time_seconds: int = 0) -> List[Dict[str, Any]]:
        try:
            queue_url = self.get_queue_url(queue_name)
            if not queue_url:
                return []
            
            response = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = []
            for msg in response.get('Messages', []):
                messages.append({
                    'message_id': msg['MessageId'],
                    'receipt_handle': msg['ReceiptHandle'],
                    'body': json.loads(msg['Body']),
                    'attributes': msg.get('Attributes', {}),
                    'message_attributes': msg.get('MessageAttributes', {})
                })
            
            return messages
            
        except ClientError as e:
            return []
    
    # This deletes a processed message from the queue
    # Must be called after successfully processing to prevent redelivery
    def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        try:
            queue_url = self.get_queue_url(queue_name)
            if not queue_url:
                return False
            
            self.sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            return True
            
        except ClientError as e:
            return False
    
    def purge_queue(self, queue_name: str) -> bool:
        try:
            queue_url = self.get_queue_url(queue_name)
            if not queue_url:
                return False
            
            self.sqs_client.purge_queue(QueueUrl=queue_url)
            return True
            
        except ClientError as e:
            return False
    
    def delete_queue(self, queue_name: str) -> bool:
        try:
            queue_url = self.get_queue_url(queue_name)
            if not queue_url:
                return False
            
            self.sqs_client.delete_queue(QueueUrl=queue_url)
            return True
            
        except ClientError as e:
            return False
