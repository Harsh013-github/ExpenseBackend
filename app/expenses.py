# This module handles all expense-related CRUD operations
# It provides endpoints for creating, reading, updating, and deleting expenses
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from .utils import ok, bad
from .auth import get_current_user
from .dynamodb_client import get_db_client

router = APIRouter(prefix="/expenses", tags=["Expenses"])

# This initializes the DynamoDB client for expense data operations
db = None
try:
    db = get_db_client()
except Exception as e:
    pass

# This defines the data structure for creating a new expense
# All fields are validated using Pydantic for type safety and constraints
class ExpenseCreate(BaseModel):
    user_id: str = Field(..., description="User ID who created the expense")
    expense_date: str = Field(..., description="Date of expense (ISO format)")
    amount: float = Field(..., gt=0, description="Expense amount (must be positive)")
    category: Optional[str] = Field(None, max_length=100, description="Expense category")
    merchant: Optional[str] = Field(None, max_length=200, description="Merchant/vendor name")
    note: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    attachments: Optional[dict] = Field(None, description="Attachment metadata (receipts, etc.)")

# This defines the data structure for updating an existing expense
# All fields are optional to allow partial updates
class ExpenseUpdate(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID who created the expense")
    expense_date: Optional[str] = Field(None, description="Date of expense (ISO format)")
    amount: Optional[float] = Field(None, gt=0, description="Expense amount")
    category: Optional[str] = Field(None, max_length=100, description="Expense category")
    merchant: Optional[str] = Field(None, max_length=200, description="Merchant/vendor name")
    note: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    attachments: Optional[dict] = Field(None, description="Attachment metadata")

# This endpoint retrieves expenses with optional filtering by user ID or category
# Supports pagination with configurable limit (max 500 items)
@router.get("/")
def get_all_expenses(
    current=Depends(get_current_user),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results")
):
    try:
        if user_id:
            expenses = db.get_expenses_by_user(user_id, limit=limit)
        elif category:
            expenses = db.get_expenses_by_category(category, limit=limit)
        else:
            expenses = db.get_all_expenses(limit=limit)
        
        return ok("Expenses fetched successfully", expenses)
    except Exception as e:
        return bad(500, "DATABASE_ERROR", "Failed to fetch expenses", str(e))

# This endpoint creates a new expense record in DynamoDB
# It validates the data and generates a unique ID and timestamp
@router.post("/", status_code=201)
def create_expense(body: ExpenseCreate, current=Depends(get_current_user)):
    try:
        expense_data = body.model_dump(mode="json")
        expense_data = jsonable_encoder(expense_data)
        
        expense = db.create_expense(expense_data)
        
        return ok("Expense created successfully", expense, status_code=201)
        
    except ValueError as e:
        return bad(400, "VALIDATION_ERROR", str(e))
    except Exception as e:
        return bad(500, "DATABASE_ERROR", "Failed to create expense", str(e))

# This endpoint retrieves a single expense by its unique ID
# Returns 404 if the expense doesn't exist
@router.get("/{expense_id}")
def get_expense_by_id(expense_id: str, current=Depends(get_current_user)):
    try:
        expense = db.get_expense_by_id(expense_id)
        if not expense:
            return bad(404, "NOT_FOUND", "Expense not found")
        
        return ok("Expense found", expense)
        
    except Exception as e:
        return bad(500, "DATABASE_ERROR", "Failed to fetch expense", str(e))

# This endpoint updates an existing expense with partial data
# Only provided fields are updated, others remain unchanged
@router.put("/{expense_id}")
def update_expense_by_id(expense_id: str, body: ExpenseUpdate, current=Depends(get_current_user)):
    try:
        existing_expense = db.get_expense_by_id(expense_id)
        if not existing_expense:
            return bad(404, "NOT_FOUND", "Expense not found")
        
        update_data = body.model_dump(mode="json", exclude_none=True)
        update_data = jsonable_encoder(update_data)
        
        if not update_data:
            return bad(400, "NO_DATA", "No update data provided")
        
        updated_expense = db.update_expense(expense_id, update_data)
        
        return ok("Expense updated successfully", updated_expense)
        
    except ValueError as e:
        return bad(400, "VALIDATION_ERROR", str(e))
    except Exception as e:
        return bad(500, "DATABASE_ERROR", "Failed to update expense", str(e))

# This endpoint permanently deletes an expense by its ID
# Requires confirmation from the frontend to prevent accidental deletions
@router.delete("/{expense_id}")
def delete_expense_by_id(expense_id: str, current=Depends(get_current_user)):
    try:
        existing_expense = db.get_expense_by_id(expense_id)
        if not existing_expense:
            return bad(404, "NOT_FOUND", "Expense not found")
        
        success = db.delete_expense(expense_id)
        if not success:
            return bad(500, "DELETE_FAILED", "Failed to delete expense")
        
        return ok("Expense deleted successfully", {"id": expense_id})
        
    except Exception as e:
        return bad(500, "DATABASE_ERROR", "Failed to delete expense", str(e))
