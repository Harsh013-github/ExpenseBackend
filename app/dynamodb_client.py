# This module provides a client for interacting with AWS DynamoDB
# It handles user profiles and expense data with proper error handling
import boto3
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

# This class encapsulates all DynamoDB operations for the application
class DynamoDBClient:
    def __init__(self):
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS credentials not found in environment variables")
        
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.aws_region
        )
        
        self.user_profiles = self.dynamodb.Table('user_profiles')
        self.finance_expenses = self.dynamodb.Table('finance_expenses')
    
    # This converts Decimal types from DynamoDB to Python int/float for JSON serialization
    def _convert_decimals(self, obj):
        if isinstance(obj, list):
            return [self._convert_decimals(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._convert_decimals(value) for key, value in obj.items()}
        elif isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        else:
            return obj
    
    # This converts Python float types to Decimal for DynamoDB storage
    def _prepare_item(self, item: Dict) -> Dict:
        if isinstance(item, dict):
            return {k: self._prepare_item(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [self._prepare_item(i) for i in item]
        elif isinstance(item, float):
            return Decimal(str(item))
        else:
            return item
    
    # ==================== USER PROFILE MANAGEMENT ====================
    
    # This creates a new user profile in DynamoDB with email and name
    def create_user_profile(self, email: str, name: str, password_hash: str = None) -> Dict:
        user_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        item = {
            'id': user_id,
            'email': email,
            'name': name,
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        if password_hash:
            item['password_hash'] = password_hash
        
        try:
            self.user_profiles.put_item(
                Item=self._prepare_item(item),
                ConditionExpression='attribute_not_exists(id)'
            )
            return self._convert_decimals(item)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError("User with this ID already exists")
            raise e
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        try:
            response = self.user_profiles.get_item(Key={'id': user_id})
            return self._convert_decimals(response.get('Item'))
        except ClientError:
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        try:
            response = self.user_profiles.query(
                IndexName='email-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email)
            )
            items = response.get('Items', [])
            return self._convert_decimals(items[0]) if items else None
        except ClientError:
            return None
    
    def update_user_profile(self, user_id: str, updates: Dict) -> Optional[Dict]:
        timestamp = datetime.utcnow().isoformat() + 'Z'
        updates['updated_at'] = timestamp
        
        update_expr = "SET "
        expr_attr_values = {}
        expr_attr_names = {}
        
        for key, value in updates.items():
            safe_key = f"#{key}"
            value_key = f":{key}"
            expr_attr_names[safe_key] = key
            expr_attr_values[value_key] = self._prepare_item(value)
            update_expr += f"{safe_key} = {value_key}, "
        
        update_expr = update_expr.rstrip(", ")
        
        try:
            response = self.user_profiles.update_item(
                Key={'id': user_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
                ReturnValues='ALL_NEW'
            )
            return self._convert_decimals(response.get('Attributes'))
        except ClientError:
            return None
    
    def delete_user_profile(self, user_id: str) -> bool:
        try:
            self.user_profiles.delete_item(Key={'id': user_id})
            return True
        except ClientError:
            return False
    
    # ==================== EXPENSE MANAGEMENT ====================
    
    # This creates a new expense record with auto-generated ID and timestamps
    def create_expense(self, expense_data: Dict) -> Dict:
        expense_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        item = {
            'id': expense_id,
            'created_at': timestamp,
            'updated_at': timestamp,
            **expense_data
        }
        
        try:
            self.finance_expenses.put_item(
                Item=self._prepare_item(item),
                ConditionExpression='attribute_not_exists(id)'
            )
            return self._convert_decimals(item)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError("Expense with this ID already exists")
            raise e
    
    # This retrieves a single expense by its unique ID
    def get_expense_by_id(self, expense_id: str) -> Optional[Dict]:
        try:
            response = self.finance_expenses.get_item(Key={'id': expense_id})
            return self._convert_decimals(response.get('Item'))
        except ClientError:
            return None
    
    # This queries all expenses for a specific user using the user_id index
    def get_expenses_by_user(self, user_id: str, limit: int = 100) -> List[Dict]:
        try:
            response = self.finance_expenses.query(
                IndexName='user_id-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id),
                Limit=limit
            )
            return self._convert_decimals(response.get('Items', []))
        except ClientError:
            return []
    
    # This queries all expenses in a specific category using the category index
    def get_expenses_by_category(self, category: str, limit: int = 100) -> List[Dict]:
        try:
            response = self.finance_expenses.query(
                IndexName='category-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('category').eq(category),
                Limit=limit
            )
            return self._convert_decimals(response.get('Items', []))
        except ClientError:
            return []
    
    def get_all_expenses(self, limit: int = 100) -> List[Dict]:
        try:
            response = self.finance_expenses.scan(Limit=limit)
            return self._convert_decimals(response.get('Items', []))
        except ClientError:
            return []
    
    def update_expense(self, expense_id: str, updates: Dict) -> Optional[Dict]:
        timestamp = datetime.utcnow().isoformat() + 'Z'
        updates['updated_at'] = timestamp
        
        update_expr = "SET "
        expr_attr_values = {}
        expr_attr_names = {}
        
        for key, value in updates.items():
            safe_key = f"#{key}"
            value_key = f":{key}"
            expr_attr_names[safe_key] = key
            expr_attr_values[value_key] = self._prepare_item(value)
            update_expr += f"{safe_key} = {value_key}, "
        
        update_expr = update_expr.rstrip(", ")
        
        try:
            response = self.finance_expenses.update_item(
                Key={'id': expense_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
                ReturnValues='ALL_NEW'
            )
            return self._convert_decimals(response.get('Attributes'))
        except ClientError:
            return None
    
    def delete_expense(self, expense_id: str) -> bool:
        try:
            self.finance_expenses.delete_item(Key={'id': expense_id})
            return True
        except ClientError:
            return False

    
    def health_check(self) -> Dict:
        try:
            user_response = self.user_profiles.scan(Limit=1)
            user_count = user_response['Count']
            
            expense_response = self.finance_expenses.scan(Limit=1)
            expense_count = expense_response['Count']
            
            return {
                'status': 'healthy',
                'user_profiles': f"{user_count} items accessible",
                'finance_expenses': f"{expense_count} items accessible",
                'region': self.aws_region
            }
        except ClientError as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

db_client = None

def get_db_client() -> DynamoDBClient:
    global db_client
    if db_client is None:
        db_client = DynamoDBClient()
    return db_client