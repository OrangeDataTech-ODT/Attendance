# Email Functionality Guide

## Overview

The email functionality has been updated to support three modes of sending attendance report emails, with proper empcode matching that handles zero-padding differences.

## Key Features

### 1. Empcode Normalization
- **Problem**: API returns empcodes with leading zeros (e.g., "0021", "0004"), but the database may store them without zeros (e.g., "21", "4")
- **Solution**: Created `normalize_empcode()` and `find_employee_by_empcode()` utility functions that handle zero-padding differences
- **Usage**: Automatically handles matching between API data and database records

### 2. Three Email Modes

#### Mode 1: Single Email
Send email to one email address entered by the user.

**Request Format:**
```json
{
  "mode": "single",
  "email": "employee@example.com",
  "empcode": "0021",  // Optional
  "employeeName": "John Doe",  // Optional
  "fromDate": "2024-01-01",
  "toDate": "2024-01-31",
  "attendanceData": [...],
  "customMessage": "Optional custom message"
}
```

**Features:**
- If `empcode` is provided, the system will try to fetch employee name from database
- If employee found in database, uses email from database (if available)
- Otherwise uses the provided email address

#### Mode 2: Multiple Emails
Send emails to multiple email addresses (comma-separated).

**Request Format:**
```json
{
  "mode": "multiple",
  "emails": "email1@example.com,email2@example.com,email3@example.com",
  "fromDate": "2024-01-01",
  "toDate": "2024-01-31",
  "attendanceData": [...],
  "customMessage": "Optional custom message"
}
```

**Features:**
- Accepts comma-separated email addresses
- Sends the same attendance data to all emails
- Returns success/failure status for each email

#### Mode 3: Email to All
Automatically fetch emails from `employee_details` table based on empcodes in attendance data.

**Request Format:**
```json
{
  "mode": "all",
  "fromDate": "2024-01-01",
  "toDate": "2024-01-31",
  "attendanceData": [
    {"empcode": "0021", "name": "John Doe", ...},
    {"empcode": "0004", "name": "Jane Smith", ...},
    ...
  ],
  "customMessage": "Optional custom message"
}
```

**Features:**
- Automatically extracts unique empcodes from attendance data
- Matches empcodes with `employee_details` table (handles zero-padding)
- Sends personalized emails to each employee with their own attendance data
- Only sends to employees who have email addresses in the database
- Returns list of employees found/not found

## API Endpoint

**URL:** `/email/send-attendance/`

**Method:** `POST`

**Content-Type:** `application/json`

## Response Format

### Success Response (Single Mode)
```json
{
  "status": "success",
  "message": "Attendance report email sent successfully",
  "data": {
    "mode": "single",
    "email": "employee@example.com",
    "empcode": "0021",
    "employeeName": "John Doe",
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "recordsCount": 20
  }
}
```

### Success Response (Multiple Mode)
```json
{
  "status": "success",
  "message": "Sent 2 email(s), 1 failed",
  "data": {
    "mode": "multiple",
    "totalEmails": 3,
    "successCount": 2,
    "failedCount": 1,
    "successEmails": ["email1@example.com", "email2@example.com"],
    "failedEmails": [
      {
        "email": "email3@example.com",
        "reason": "Email sending failed"
      }
    ],
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "recordsCount": 20
  }
}
```

### Success Response (All Mode)
```json
{
  "status": "success",
  "message": "Sent 5 email(s), 0 failed",
  "data": {
    "mode": "all",
    "totalEmployeesFound": 5,
    "successCount": 5,
    "failedCount": 0,
    "employeesNotFound": ["0025"],
    "successEmails": [
      {
        "email": "john@example.com",
        "empcode": "0021",
        "employeeName": "John Doe"
      },
      ...
    ],
    "failedEmails": [],
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "totalRecords": 20
  }
}
```

## Empcode Matching Logic

The system uses a smart matching algorithm that handles zero-padding differences:

1. **Direct Match**: Tries exact match first
2. **Normalized Match**: Removes leading zeros from both sides and compares
3. **Zero-Padded Match**: Tries padding the search term to 4 digits
4. **Reverse Match**: Tries removing zeros from search term and matching with padded DB values

**Examples:**
- API has "0021", DB has "21" → ✅ Match
- API has "0004", DB has "4" → ✅ Match
- API has "21", DB has "0021" → ✅ Match
- API has "4", DB has "0004" → ✅ Match

## Database Requirements

For "Email to All" mode to work:
1. Employees must be in the `employee_details` table
2. Employees must have valid email addresses
3. Empcodes in attendance data must match (after normalization) with empcodes in database

## Error Handling

### Missing Required Fields
```json
{
  "status": "error",
  "message": "Missing required fields: fromDate and toDate are required"
}
```

### Invalid Email Format
```json
{
  "status": "error",
  "message": "Invalid email format"
}
```

### No Employees Found (All Mode)
```json
{
  "status": "error",
  "message": "No employees with email addresses found in database for empcodes: 0021, 0004",
  "data": {
    "empcodesChecked": ["0021", "0004"],
    "employeesNotFound": ["0021", "0004"]
  }
}
```

## Frontend Integration

### Example: Single Email Mode
```javascript
const response = await fetch('/email/send-attendance/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    mode: 'single',
    email: 'employee@example.com',
    empcode: '0021',
    employeeName: 'John Doe',
    fromDate: '2024-01-01',
    toDate: '2024-01-31',
    attendanceData: [...],
    customMessage: 'Your attendance report'
  })
});
```

### Example: Multiple Emails Mode
```javascript
const response = await fetch('/email/send-attendance/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    mode: 'multiple',
    emails: 'email1@example.com,email2@example.com,email3@example.com',
    fromDate: '2024-01-01',
    toDate: '2024-01-31',
    attendanceData: [...]
  })
});
```

### Example: Email to All Mode
```javascript
const response = await fetch('/email/send-attendance/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    mode: 'all',
    fromDate: '2024-01-01',
    toDate: '2024-01-31',
    attendanceData: [
      {empcode: '0021', name: 'John Doe', ...},
      {empcode: '0004', name: 'Jane Smith', ...},
      ...
    ]
  })
});
```

## Updated Files

1. **dj_app/utils/email_service.py**
   - Added `normalize_empcode()` function
   - Added `find_employee_by_empcode()` function

2. **dj_app/views/email_views.py**
   - Completely rewritten `SendAttendanceEmailAPI` class
   - Added three mode handlers: `_send_single_email()`, `_send_multiple_emails()`, `_send_email_to_all()`

3. **dj_app/views/punch_monitoring_views.py**
   - Updated to use `find_employee_by_empcode()` for empcode matching

4. **dj_app/management/commands/monitor_punches.py**
   - Updated to use `find_employee_by_empcode()` for empcode matching

## Testing

### Test Single Email Mode
```bash
curl -X POST http://localhost:8000/email/send-attendance/ \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "single",
    "email": "test@example.com",
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "attendanceData": [{"empcode": "0021", "name": "Test User"}]
  }'
```

### Test Multiple Emails Mode
```bash
curl -X POST http://localhost:8000/email/send-attendance/ \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "multiple",
    "emails": "test1@example.com,test2@example.com",
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "attendanceData": [{"empcode": "0021", "name": "Test User"}]
  }'
```

### Test Email to All Mode
```bash
curl -X POST http://localhost:8000/email/send-attendance/ \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "all",
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "attendanceData": [
      {"empcode": "0021", "name": "John Doe"},
      {"empcode": "0004", "name": "Jane Smith"}
    ]
  }'
```

## Notes

- Default mode is "single" if not specified
- All modes require `fromDate`, `toDate`, and `attendanceData`
- Date formats are flexible (YYYY-MM-DD, DD/MM/YYYY, etc.)
- Empcode matching is case-insensitive and handles zero-padding automatically
- Only active employees with email addresses will receive emails in "all" mode

