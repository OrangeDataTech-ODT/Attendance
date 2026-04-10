# Empcode Matching Fix

## Problem
The database stores empcodes **without leading zeros** (e.g., "21", "4", "18"), but the API returns empcodes **with leading zeros** (e.g., "0021", "0004", "0018"). This mismatch was causing emails not to be sent in "Email to All" mode.

## Solution
Updated the `find_employee_by_empcode()` function to handle zero-padding differences using multiple matching strategies:

1. **Direct Match**: Tries exact match first
2. **Normalized Match**: Removes leading zeros and matches (most common case)
3. **Zero-Padded Match**: Pads to 4 digits and matches
4. **Iterative Normalized Match**: Fallback for edge cases

## How It Works

### Example 1: API "0021" → DB "21"
```
1. Direct match: "0021" == "21" → No match
2. Normalized match: normalize("0021") = "21", DB has "21" → ✅ Match!
```

### Example 2: API "0004" → DB "4"
```
1. Direct match: "0004" == "4" → No match
2. Normalized match: normalize("0004") = "4", DB has "4" → ✅ Match!
```

### Example 3: API "21" → DB "0021" (reverse case)
```
1. Direct match: "21" == "0021" → No match
2. Normalized match: normalize("21") = "21", DB has "0021" → No match
3. Zero-padded match: "21".zfill(4) = "0021", DB has "0021" → ✅ Match!
```

## Testing

### Test the Matching Function

You can test the empcode matching by calling the email API with "all" mode:

```bash
curl -X POST http://localhost:8000/email/send-attendance/ \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "all",
    "fromDate": "2024-01-01",
    "toDate": "2024-01-31",
    "attendanceData": [
      {"empcode": "0021", "name": "Employee 21"},
      {"empcode": "0004", "name": "Employee 4"},
      {"empcode": "0010", "name": "Employee 10"},
      {"empcode": "0008", "name": "Employee 8"},
      {"empcode": "0014", "name": "Employee 14"},
      {"empcode": "0002", "name": "Employee 2"},
      {"empcode": "0018", "name": "Employee 18"}
    ]
  }'
```

### Expected Response

If matching works correctly, you should see:
```json
{
  "status": "success",
  "message": "Sent 7 email(s), 0 failed",
  "data": {
    "mode": "all",
    "totalEmployeesFound": 7,
    "successCount": 7,
    "failedCount": 0,
    "employeesNotFound": [],
    "successEmails": [
      {
        "email": "employee21@example.com",
        "empcode": "0021",
        "employeeName": "Employee 21"
      },
      ...
    ]
  }
}
```

### Check Logs

The logs will show the matching process:
```
INFO: Looking up 7 unique empcodes from attendance data: ['0021', '0004', '0010', '0008', '0014', '0002', '0018']
DEBUG: Searching for employee with empcode: 0021
DEBUG: Found employee with normalized match: 0021 -> 21 -> 21
INFO: Found employee: Employee 21 (DB empcode: 21, API empcode: 0021)
INFO: Added employee Employee 21 (employee21@example.com) with X attendance records
```

## Database Requirements

For "Email to All" mode to work:
1. Employees must exist in `employee_details` table
2. Empcodes in database: "21", "4", "10", "8", "14", "2", "18" (without leading zeros)
3. Employees must have valid email addresses
4. API empcodes: "0021", "0004", "0010", "0008", "0014", "0002", "0018" (with leading zeros)

## Verification Checklist

- [x] `normalize_empcode()` function removes leading zeros correctly
- [x] `find_employee_by_empcode()` tries multiple matching strategies
- [x] Email views use `find_employee_by_empcode()` for all lookups
- [x] Monitor punches command uses normalized matching
- [x] Punch monitoring views use normalized matching
- [x] Added debug logging to track matching process

## Common Issues

### Issue: "No employees with email addresses found"
**Cause**: Empcodes in attendance data don't match any employees in database
**Solution**: 
1. Check if employees exist in `employee_details` table
2. Verify empcodes match (after normalization)
3. Check logs for matching attempts

### Issue: "Employee not found in database"
**Cause**: Empcode doesn't exist in `employee_details` table
**Solution**: 
1. Add employee to `employee_details` table
2. Ensure empcode matches (can be with or without leading zeros)
3. Ensure employee has an email address

### Issue: Some employees found, others not
**Cause**: Mixed empcode formats or missing employees
**Solution**: 
1. Check logs to see which empcodes matched
2. Verify all employees exist in database
3. Check `employeesNotFound` in response

## Debugging

Enable debug logging to see the matching process:
```python
# In Django settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'dj_app.utils.email_service': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'dj_app.views.email_views': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Files Modified

1. **dj_app/utils/email_service.py**
   - Optimized `find_employee_by_empcode()` function
   - Added debug logging
   - Improved matching strategies order

2. **dj_app/views/email_views.py**
   - Added detailed logging for empcode lookup
   - Added logging for employee matching results
   - Improved error messages

## Summary

The empcode matching issue has been fixed. The system now correctly matches:
- API "0021" ↔ DB "21"
- API "0004" ↔ DB "4"
- API "0010" ↔ DB "10"
- And all other zero-padding variations

The "Email to All" mode should now work correctly with the empcode format mismatch.

