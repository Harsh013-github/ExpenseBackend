# It continuously polls the queue and processes messages asynchronously
import os
import json
import asyncio
from typing import Optional
from dotenv import load_dotenv
from .sqs_client import SQSClient
from ..sns.sns_client import SNSClient

load_dotenv()

# This worker runs in the background to process queued messages
# Used for handling file upload notifications and other async tasks
class SQSWorker:
    def __init__(self):
        try:
            self.sqs_client = SQSClient()
            self.sns_client = SNSClient()
        except Exception as e:
            self.sqs_client = None
            self.sns_client = None
        
        self.queue_name = os.getenv('SQS_S3_UPLOAD_QUEUE', 's3-upload-notification-queue')
        self.is_running = False
        self.poll_interval = int(os.getenv('SQS_POLL_INTERVAL', '5'))
        self.max_messages = int(os.getenv('SQS_MAX_MESSAGES', '10'))
    
    # This starts the background worker to begin processing messages
    def start(self):
        if self.is_running or not self.sqs_client:
            return
            
        queue_url = self.sqs_client.get_queue_url(self.queue_name)
        if not queue_url:
            return
            
        self.is_running = True
        
    def stop(self):
        self.is_running = False
    
    # This continuously polls the SQS queue and processes incoming messages
    # Runs in an async loop with configurable polling interval
    async def process_messages(self):
        if not self.sqs_client:
            return
            
        while self.is_running:
            try:
                messages = self.sqs_client.receive_messages(
                    self.queue_name,
                    max_messages=self.max_messages,
                    wait_time_seconds=self.poll_interval
                )
                
                if messages:
                    for message in messages:
                        await self._process_message(message)
                else:
                    await asyncio.sleep(self.poll_interval)
                    
            except Exception as e:
                await asyncio.sleep(self.poll_interval)
                
    async def _process_message(self, message: dict):
        try:
            receipt_handle = message.get('receipt_handle')
            message_id = message.get('message_id')
            body = message.get('body', {})
            
            file_key = body.get('file_key')
            uploader_id = body.get('uploader_id')
            
            if not file_key:
                self._delete_message(receipt_handle)
                return
            
            self._delete_message(receipt_handle)
            
        except Exception as e:
            pass
            
    def _delete_message(self, receipt_handle: str):
        try:
            if receipt_handle:
                self.sqs_client.delete_message(self.queue_name, receipt_handle)
        except Exception as e:
            pass


# Global worker instance
_worker_instance: Optional[SQSWorker] = None
_worker_task: Optional[asyncio.Task] = None


def get_worker() -> SQSWorker:
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = SQSWorker()
    return _worker_instance


async def start_worker():
    global _worker_task
    
    if _worker_task is not None and not _worker_task.done():
        return
        
    worker = get_worker()
    worker.start()
    
    _worker_task = asyncio.create_task(worker.process_messages())


async def stop_worker():
    global _worker_task, _worker_instance
    
    if _worker_instance:
        _worker_instance.stop()
        
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
