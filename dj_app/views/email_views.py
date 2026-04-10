"""
Email views for sending attendance reports and notifications
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from datetime import datetime
import re

from ..utils.email_service import send_attendance_email, find_employee_by_empcode, normalize_empcode
from ..models.employee import Employee

logger = logging.getLogger(__name__)


def parse_date(date_string):
    """
    Parse date string in various formats and return YYYY-MM-DD format
    
    Handles:
    - YYYY-MM-DD
    - ISO datetime strings (YYYY-MM-DDTHH:MM:SS...)
    - ISO datetime with timezone (YYYY-MM-DDTHH:MM:SSZ or +HH:MM)
    - Timestamps
    """
    if not date_string:
        return None
    
    # If it's already a string, try to parse it
    if isinstance(date_string, str):
        # Remove whitespace
        date_string = date_string.strip()
        
        # Try strict YYYY-MM-DD format first
        try:
            datetime.strptime(date_string, '%Y-%m-%d')
            return date_string
        except ValueError:
            pass
        
        # Try to extract date part from ISO datetime string (YYYY-MM-DDTHH:MM:SS...)
        if 'T' in date_string:
            date_part = date_string.split('T')[0]
            # Remove timezone info if present (Z or +HH:MM or -HH:MM)
            if '+' in date_part or date_part.endswith('Z'):
                # Already split by T, so date_part should be clean
                pass
            try:
                datetime.strptime(date_part, '%Y-%m-%d')
                return date_part
            except ValueError:
                pass
        
        # Try other common formats
        # Format: YYYY/MM/DD
        if '/' in date_string:
            date_part = date_string.split()[0]  # Get date part if there's time info
            parts = date_part.split('/')
            
            # Try YYYY/MM/DD format
            if len(parts) == 3:
                try:
                    # Check if first part is 4 digits (likely YYYY)
                    if len(parts[0]) == 4:
                        parsed = datetime.strptime(date_part, '%Y/%m/%d')
                        return parsed.strftime('%Y-%m-%d')
                except ValueError:
                    pass
                
                # Try DD/MM/YYYY format (common in many countries)
                try:
                    parsed = datetime.strptime(date_part, '%d/%m/%Y')
                    return parsed.strftime('%Y-%m-%d')
                except ValueError:
                    pass
                
                # Try MM/DD/YYYY format (US format)
                try:
                    parsed = datetime.strptime(date_part, '%m/%d/%Y')
                    return parsed.strftime('%Y-%m-%d')
                except ValueError:
                    pass
        
        # Try to extract date using regex (YYYY-MM-DD pattern)
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        match = re.search(date_pattern, date_string)
        if match:
            try:
                datetime.strptime(match.group(1), '%Y-%m-%d')
                return match.group(1)
            except ValueError:
                pass
        
        # Log the problematic format for debugging
        logger.warning(f"Could not parse date string: {date_string}")
        return None
    
    return None


class SendAttendanceEmailAPI(APIView):
    """
    API endpoint to send attendance report emails
    
    Supports three modes:
    1. Single Email: Send to one email address (user enters email)
    2. Multiple Emails: Send to multiple email addresses (comma-separated)
    3. Email to All: Automatically fetch emails from employee_details table based on empcodes
    
    Accepts POST request with:
    - mode: 'single', 'multiple', or 'all' (default: 'single')
    - email: Single email address (for 'single' mode)
    - emails: Comma-separated email addresses (for 'multiple' mode)
    - empcode: Employee code (optional, used for 'single' and 'multiple' modes)
    - employeeName: Employee name (optional, used for 'single' and 'multiple' modes)
    - fromDate: Start date (YYYY-MM-DD format) - REQUIRED
    - toDate: End date (YYYY-MM-DD format) - REQUIRED
    - attendanceData: Array of attendance records - REQUIRED
    - customMessage: (Optional) Custom message to include after the period line
    """
    
    def post(self, request):
        """
        Send attendance report email(s) based on mode
        """
        return Response(
            {
                "status": "error",
                "message": "Email functionality is disabled on this server.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

        try:
            # Log incoming request for debugging
            logger.debug(f"Email API request data keys: {list(request.data.keys())}")
            logger.debug(f"Email API request data: {request.data}")
            
            # Extract mode - check if explicitly provided, otherwise auto-detect
            mode = request.data.get('mode', '').lower()
            
            # Auto-detect mode based on request data (backward compatibility)
            if not mode:
                # If 'emails' (plural) is provided, use 'multiple' mode
                if 'emails' in request.data and request.data.get('emails'):
                    mode = 'multiple'
                # If 'email' (singular) is provided, use 'single' mode
                elif 'email' in request.data and request.data.get('email'):
                    mode = 'single'
                # Check if attendanceData has empcodes
                elif 'attendanceData' in request.data and isinstance(request.data.get('attendanceData'), list):
                    attendance_data_temp = request.data.get('attendanceData', [])
                    if attendance_data_temp and isinstance(attendance_data_temp[0], dict):
                        # Check if any record has empcode
                        has_empcode = any(
                            rec.get('empcode') or rec.get('Empcode') or rec.get('EmpCode')
                            for rec in attendance_data_temp if isinstance(rec, dict)
                        )
                        # Count unique empcodes
                        unique_empcodes = set()
                        for rec in attendance_data_temp:
                            if isinstance(rec, dict):
                                emp = rec.get('empcode') or rec.get('Empcode') or rec.get('EmpCode')
                                if emp:
                                    unique_empcodes.add(str(emp))
                        
                        # If has empcodes and no email field, use 'all' mode
                        # Also use 'all' if there are multiple unique empcodes
                        if has_empcode and ('email' not in request.data or len(unique_empcodes) > 1):
                            mode = 'all'
                        else:
                            mode = 'single'
                    else:
                        mode = 'single'
                # If empcode is provided in request but no email, try to fetch from DB (single mode)
                elif 'empcode' in request.data and request.data.get('empcode') and 'email' not in request.data:
                    mode = 'single'  # Will try to fetch email from database
                else:
                    # Default to 'all' if no email field is provided (likely email to all)
                    if 'email' not in request.data:
                        mode = 'all'
                    else:
                        mode = 'single'
            
            logger.info(f"Detected email mode: {mode} (email field present: {'email' in request.data}, empcode in request: {'empcode' in request.data})")
            
            # Extract common fields
            from_date = request.data.get('fromDate') or request.data.get('from_date')
            to_date = request.data.get('toDate') or request.data.get('to_date')
            attendance_data = request.data.get('attendanceData') or request.data.get('attendance_data') or []
            custom_message = request.data.get('customMessage') or request.data.get('custom_message') or request.data.get('message')
            
            # Validate required fields
            if not from_date or not to_date:
                logger.warning(f"Missing date fields - fromDate: {from_date}, toDate: {to_date}")
                return Response({
                    'status': 'error',
                    'message': 'Missing required fields: fromDate and toDate are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not isinstance(attendance_data, list):
                logger.warning(f"attendanceData is not a list: {type(attendance_data)}")
                return Response({
                    'status': 'error',
                    'message': 'attendanceData must be an array'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if len(attendance_data) == 0:
                logger.warning("attendanceData is empty")
                return Response({
                    'status': 'error',
                    'message': 'attendanceData must be a non-empty array'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse and validate date format
            if not isinstance(from_date, str):
                from_date = str(from_date)
            if not isinstance(to_date, str):
                to_date = str(to_date)
            
            parsed_from_date = parse_date(from_date)
            parsed_to_date = parse_date(to_date)
            
            if not parsed_from_date:
                return Response({
                    'status': 'error',
                    'message': f'Invalid fromDate format: {from_date}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not parsed_to_date:
                return Response({
                    'status': 'error',
                    'message': f'Invalid toDate format: {to_date}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from_date = parsed_from_date
            to_date = parsed_to_date
            
            # Handle different modes
            if mode == 'single':
                return self._send_single_email(request, from_date, to_date, attendance_data, custom_message)
            elif mode == 'multiple':
                return self._send_multiple_emails(request, from_date, to_date, attendance_data, custom_message)
            elif mode == 'all':
                return self._send_email_to_all(request, from_date, to_date, attendance_data, custom_message)
            else:
                return Response({
                    'status': 'error',
                    'message': f'Invalid mode: {mode}. Must be "single", "multiple", or "all"'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in SendAttendanceEmailAPI: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _send_single_email(self, request, from_date, to_date, attendance_data, custom_message):
        """Send email to a single email address"""
        email = request.data.get('email')
        empcode = request.data.get('empcode', '')
        employee_name = request.data.get('employeeName') or request.data.get('employee_name', 'Employee')
        
        # If no email provided, try to get from employee_details table using empcode
        if not email:
            # Try to get empcode from request or from attendance data
            if not empcode and attendance_data:
                # Extract empcode from first attendance record
                first_record = attendance_data[0] if isinstance(attendance_data[0], dict) else {}
                empcode = first_record.get('empcode') or first_record.get('Empcode') or first_record.get('EmpCode') or ''
            
            if empcode:
                logger.info(f"No email provided, trying to fetch from employee_details for empcode: {empcode}")
                employee = find_employee_by_empcode(empcode)
                if employee and employee.email:
                    email = employee.email
                    employee_name = employee.name
                    logger.info(f"Found employee email from database: {email} for empcode {empcode}")
                else:
                    logger.warning(f"Employee not found or no email for empcode: {empcode}")
        
        if not email:
            return Response({
                'status': 'error',
                'message': 'Missing required field: email. Provide email address or ensure empcode exists in employee_details table with email.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email format
        if '@' not in email:
            return Response({
                'status': 'error',
                'message': 'Invalid email format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # If empcode provided, try to get employee name from database
        if empcode:
            employee = find_employee_by_empcode(empcode)
            if employee:
                employee_name = employee.name
                # Use email from database if available, otherwise use provided email
                if employee.email:
                    email = employee.email
        
        success = send_attendance_email(
            employee_email=email,
            employee_name=employee_name,
            empcode=empcode or 'N/A',
            from_date=from_date,
            to_date=to_date,
            attendance_data=attendance_data,
            custom_message=custom_message
        )
        
        if success:
            return Response({
                'status': 'success',
                'message': 'Attendance report email sent successfully',
                'data': {
                    'mode': 'single',
                    'email': email,
                    'empcode': empcode,
                    'employeeName': employee_name,
                    'fromDate': from_date,
                    'toDate': to_date,
                    'recordsCount': len(attendance_data)
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': 'Failed to send email. Please check server logs for details.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _send_multiple_emails(self, request, from_date, to_date, attendance_data, custom_message):
        """Send emails to multiple email addresses"""
        emails_str = request.data.get('emails', '')
        
        if not emails_str:
            return Response({
                'status': 'error',
                'message': 'Missing required field: emails (comma-separated, for multiple mode)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse comma-separated emails
        email_list = [email.strip() for email in emails_str.split(',') if email.strip()]
        
        if not email_list:
            return Response({
                'status': 'error',
                'message': 'No valid email addresses provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email formats
        invalid_emails = [email for email in email_list if '@' not in email]
        if invalid_emails:
            return Response({
                'status': 'error',
                'message': f'Invalid email format(s): {", ".join(invalid_emails)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get empcode from first attendance record if available
        empcode = ''
        employee_name = 'Employee'
        if attendance_data and isinstance(attendance_data[0], dict):
            empcode = str(attendance_data[0].get('empcode') or attendance_data[0].get('Empcode') or '')
            employee_name = str(attendance_data[0].get('name') or attendance_data[0].get('Name') or 'Employee')
        
        # Send emails to all addresses
        results = {
            'success': [],
            'failed': []
        }
        
        for email in email_list:
            try:
                success = send_attendance_email(
                    employee_email=email,
                    employee_name=employee_name,
                    empcode=empcode or 'N/A',
                    from_date=from_date,
                    to_date=to_date,
                    attendance_data=attendance_data,
                    custom_message=custom_message
                )
                
                if success:
                    results['success'].append(email)
                    logger.info(f"Email sent successfully to {email}")
                else:
                    results['failed'].append({'email': email, 'reason': 'Email sending failed'})
                    logger.error(f"Failed to send email to {email}")
            except Exception as e:
                results['failed'].append({'email': email, 'reason': str(e)})
                logger.error(f"Error sending email to {email}: {str(e)}")
        
        return Response({
            'status': 'success' if results['success'] else 'error',
            'message': f"Sent {len(results['success'])} email(s), {len(results['failed'])} failed",
            'data': {
                'mode': 'multiple',
                'totalEmails': len(email_list),
                'successCount': len(results['success']),
                'failedCount': len(results['failed']),
                'successEmails': results['success'],
                'failedEmails': results['failed'],
                'fromDate': from_date,
                'toDate': to_date,
                'recordsCount': len(attendance_data)
            }
        }, status=status.HTTP_200_OK)
    
    def _send_email_to_all(self, request, from_date, to_date, attendance_data, custom_message):
        """Send emails to all employees found in attendance data by matching with employee_details table"""
        # Extract unique empcodes from attendance data
        empcodes_set = set()
        
        for record in attendance_data:
            if isinstance(record, dict):
                empcode = record.get('empcode') or record.get('Empcode') or record.get('EmpCode')
                if empcode:
                    empcodes_set.add(str(empcode))
        
        if not empcodes_set:
            return Response({
                'status': 'error',
                'message': 'No empcodes found in attendance data'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find employees from database using normalized empcode matching
        employees_found = {}
        employees_not_found = []
        
        logger.info(f"Looking up {len(empcodes_set)} unique empcodes from attendance data: {list(empcodes_set)}")
        
        for empcode in empcodes_set:
            logger.debug(f"Searching for employee with empcode: {empcode}")
            employee = find_employee_by_empcode(empcode)
            if employee:
                logger.info(f"Found employee: {employee.name} (DB empcode: {employee.empcode}, API empcode: {empcode})")
                if employee.email:
                # Group attendance data by empcode (normalized matching)
                    normalized_search_empcode = normalize_empcode(empcode)
                    employee_attendance = []
                for rec in attendance_data:
                    if isinstance(rec, dict):
                        rec_empcode = rec.get('empcode') or rec.get('Empcode') or rec.get('EmpCode') or ''
                        if rec_empcode and normalize_empcode(str(rec_empcode)) == normalized_search_empcode:
                            employee_attendance.append(rec)
                
                    employees_found[employee.email] = {
                        'employee': employee,
                        'empcode': empcode,  # Keep original API empcode for reference
                        'db_empcode': employee.empcode,  # Store DB empcode for logging
                        'attendance_data': employee_attendance if employee_attendance else attendance_data
                    }
                    logger.info(f"Added employee {employee.name} ({employee.email}) with {len(employee_attendance if employee_attendance else attendance_data)} attendance records")
                else:
                    logger.warning(f"Employee {employee.name} (empcode: {employee.empcode}) found but has no email address")
                    employees_not_found.append(empcode)
            else:
                logger.warning(f"Employee not found in database for empcode: {empcode}")
                employees_not_found.append(empcode)
        
        if not employees_found:
            return Response({
                'status': 'error',
                'message': f'No employees with email addresses found in database for empcodes: {", ".join(empcodes_set)}',
                'data': {
                    'empcodesChecked': list(empcodes_set),
                    'employeesNotFound': employees_not_found
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Send emails to all found employees
        results = {
            'success': [],
            'failed': []
        }
        
        for email, employee_info in employees_found.items():
            employee = employee_info['employee']
            empcode = employee_info['empcode']
            emp_attendance_data = employee_info['attendance_data']
            
            try:
                success = send_attendance_email(
                    employee_email=email,
                    employee_name=employee.name,
                    empcode=empcode,
                    from_date=from_date,
                    to_date=to_date,
                    attendance_data=emp_attendance_data if emp_attendance_data else attendance_data,
                    custom_message=custom_message
                )
                
                if success:
                    results['success'].append({
                        'email': email,
                        'empcode': empcode,
                        'employeeName': employee.name
                    })
                    logger.info(f"Email sent successfully to {email} for employee {empcode} ({employee.name})")
                else:
                    results['failed'].append({
                        'email': email,
                        'empcode': empcode,
                        'employeeName': employee.name,
                        'reason': 'Email sending failed'
                    })
                    logger.error(f"Failed to send email to {email} for employee {empcode}")
            except Exception as e:
                results['failed'].append({
                    'email': email,
                    'empcode': empcode,
                    'employeeName': employee.name,
                    'reason': str(e)
                })
                logger.error(f"Error sending email to {email} for employee {empcode}: {str(e)}")
        
        return Response({
            'status': 'success' if results['success'] else 'error',
            'message': f"Sent {len(results['success'])} email(s), {len(results['failed'])} failed",
            'data': {
                'mode': 'all',
                'totalEmployeesFound': len(employees_found),
                'successCount': len(results['success']),
                'failedCount': len(results['failed']),
                'employeesNotFound': employees_not_found,
                'successEmails': results['success'],
                'failedEmails': results['failed'],
                'fromDate': from_date,
                'toDate': to_date,
                'totalRecords': len(attendance_data)
            }
        }, status=status.HTTP_200_OK)

