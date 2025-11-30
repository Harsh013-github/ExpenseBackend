# 💰 Finance Tracker API

A comprehensive expense tracking and financial management API built with FastAPI and AWS services. Track expenses, manage receipts, and receive real-time notifications for financial activities.

## 🚀 Technology Stack

- **FastAPI**: Modern Python web framework
- **AWS DynamoDB**: NoSQL database for expense and user data
- **AWS Cognito**: User authentication and authorization
- **AWS S3**: Receipt and attachment storage
- **AWS SNS**: Real-time expense notifications
- **AWS SQS**: Message queuing for async processing

## 📦 Installation

1. **Clone and setup environment**

```bash
cd finance_backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure AWS credentials**

```bash
cp .env.example .env
# Edit .env with your AWS credentials
```

3. **Setup AWS infrastructure**

```bash
python scripts/setup_aws_infrastructure.py
```

4. **Run the API server**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. **Start background worker (optional)**

```bash
python -m app.sqs.worker
```

**🌐 Access Points:**
- API: `http://localhost:8000`
- Interactive Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🚀 Deployment

This project includes complete CI/CD setup for **AWS Elastic Beanstalk** with **GitHub Actions**.

### Quick Deployment (3 steps, 15 minutes)

1. **Setup AWS infrastructure** (one-time)
   ```bash
   python scripts/setup_aws.py
   ```

2. **Add GitHub Secrets** (one-time)
   - Go to Repository Settings → Secrets and variables → Actions
   - Add: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `EB_BUCKET`, `AWS_REGION`
   - See `QUICK_START.md` for detailed instructions

3. **Deploy** (automatic from now on)
   ```bash
   git push origin main
   # GitHub Actions automatically tests and deploys to EB
   ```

### 📖 Deployment Documentation

- **[DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md)** - Start here! Complete overview and checklist
- **[QUICK_START.md](QUICK_START.md)** - Quick reference for common tasks
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Detailed step-by-step instructions
- **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** - Architecture and configuration details
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### CI/CD Pipeline

Automatically:
1. ✓ Runs tests on every push
2. ✓ Deploys to Elastic Beanstalk if tests pass
3. ✓ Monitors health and logs
4. ✓ Rolls back on failure

## 📚 API Endpoints

### 🔐 Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Create new user account |
| `POST` | `/api/auth/login` | User authentication |

### 💳 Expenses
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/expenses/` | List all expenses (with filters) |
| `POST` | `/api/expenses/` | Create new expense (triggers notifications) |
| `GET` | `/api/expenses/{id}` | Get expense by ID |
| `PUT` | `/api/expenses/{id}` | Update expense |
| `DELETE` | `/api/expenses/{id}` | Delete expense |
| `GET` | `/api/expenses/user/{user_id}` | Get user's expenses |
| `GET` | `/api/expenses/category/{category}` | Get expenses by category |

### �� File Management (S3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/s3/upload` | Upload receipt/attachment |
| `GET` | `/api/s3/files` | List uploaded files |
| `GET` | `/api/s3/download/{file_key}` | Download file |
| `GET` | `/api/s3/stats` | Storage statistics |

### 📧 Notifications (SQS/SNS)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sqs/notification` | Queue manual notification |
| `GET` | `/api/sqs/stats` | Queue statistics |
| `GET` | `/api/sqs/health` | Service health check |

## 🛠️ Configuration

### Environment Variables (.env)
```env
# Server Configuration  
PORT=8000
API_PREFIX=/api
ENVIRONMENT=production

# AWS Global Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# AWS DynamoDB Tables
DYNAMODB_USER_PROFILES_TABLE=user_profiles
DYNAMODB_FINANCE_EXPENSES_TABLE=finance_expenses

# AWS Services
AWS_COGNITO_USER_POOL_ID=your_user_pool_id
AWS_COGNITO_CLIENT_ID=your_client_id  
AWS_S3_BUCKET_NAME=finance-receipts-bucket

# Notifications
SNS_ENABLE_NOTIFICATIONS=true
SQS_ENABLE_NOTIFICATIONS=true
SQS_WORKER_BATCH_SIZE=5
SQS_WORKER_POLLING_INTERVAL=10
```

## 🏗️ AWS Infrastructure Setup

Use the provided scripts to set up AWS services:

```bash
# Setup all services at once
python scripts/setup_aws_infrastructure.py

# Or setup individually
python scripts/setup_dynamodb.py      # Expense and user tables
python scripts/setup_cognito.py       # User authentication  
python scripts/setup_s3.py           # Receipt storage
python scripts/setup_sns.py          # Expense notifications
python scripts/setup_sqs.py          # Message queuing
```

## 📊 Sample Usage

### User Registration
```bash
curl -X POST "http://localhost:8000/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "phone_number": "+1234567890", 
    "name": "John Doe"
  }'
```

### Create Expense (Auto-triggers Notifications)
```bash
curl -X POST "http://localhost:8000/api/expenses/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "expense_date": "2025-01-15",
    "amount": 42.50,
    "category": "Food & Dining",
    "merchant": "Starbucks",
    "note": "Team lunch meeting",
    "tags": ["business", "meals"]
  }'
```

### Upload Receipt
```bash
curl -X POST "http://localhost:8000/api/s3/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@receipt.pdf" \
  -F "bucket_name=finance-receipts-bucket"
```

### Get User Expenses
```bash
curl -X GET "http://localhost:8000/api/expenses/user/user-123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Expenses by Category
```bash
curl -X GET "http://localhost:8000/api/expenses/category/Food%20%26%20Dining" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🔄 Production Deployment

### Single Server
```bash
# Production server with multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Background worker for notifications (separate process)
python -m app.sqs.worker
```

### Process Management (PM2 Example)
```bash
# Install PM2
npm install -g pm2

# Start API server
pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000" --name finance-api

# Start background worker  
pm2 start "python -m app.sqs.worker" --name finance-worker

# Save configuration
pm2 save && pm2 startup
```

## 🏛️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   FastAPI API   │────│   AWS Cognito   │ (Authentication)
└─────────────────┘    └─────────────────┘
         │
         │              ┌─────────────────┐
         ├──────────────│   DynamoDB      │ (Expense & User Data)
         │              └─────────────────┘
         │
         │              ┌─────────────────┐
         ├──────────────│      S3         │ (Receipt Storage)  
         │              └─────────────────┘
         │
         │              ┌─────────────────┐
         └──────────────│   SNS + SQS     │ (Expense Notifications)
                        └─────────────────┘
                               │
                        ┌─────────────────┐
                        │ Background      │ (Message Processing)
                        │ Worker          │
                        └─────────────────┘
```

## 💾 Database Schema

### user_profiles Table
- **Primary Key**: `id` (String)
- **GSI**: `email-index` on `email`
- **Attributes**: id, email, full_name, avatar_url, meta, created_at, updated_at

### finance_expenses Table
- **Primary Key**: `id` (String)
- **GSI 1**: `user_id-index` on `user_id`
- **GSI 2**: `category-index` on `category`
- **Attributes**: id, user_id, expense_date, amount, category, merchant, note, tags, attachments, created_at, updated_at

## ✨ Key Features

- **🔄 Automatic Notifications**: Expense creation/updates automatically notify users
- **📧 Email Notifications**: SNS integration for reliable email delivery  
- **⚡ Background Processing**: SQS worker for non-blocking notifications
- **🔒 Secure Authentication**: JWT tokens with AWS Cognito
- **📈 Scalable Storage**: DynamoDB for high-performance data operations
- **📁 Receipt Management**: S3 integration for PDF and image receipts
- **🏷️ Expense Categorization**: Filter and organize by category, merchant, date
- **🏥 Health Checks**: Built-in service monitoring and status endpoints

## 📖 Documentation

- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc  
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

## 📄 License

MIT License
