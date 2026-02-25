"""
Email service utility for sending punch-related notifications
"""
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def normalize_empcode(empcode):
    """
    Normalize empcode by removing leading zeros for consistent matching.
    
    Examples:
    - "0021" -> "21"
    - "0004" -> "4"
    - "21" -> "21"
    - "4" -> "4"
    
    Args:
        empcode: Employee code as string or number
        
    Returns:
        Normalized empcode as string (without leading zeros)
    """
    if empcode is None:
        return None
    
    # Convert to string and strip whitespace
    empcode_str = str(empcode).strip()
    
    # Remove leading zeros
    normalized = empcode_str.lstrip('0')
    
    # If all zeros, return "0"
    if not normalized:
        return "0"
    
    return normalized


def find_employee_by_empcode(empcode):
    """
    Find employee by empcode, handling zero-padding differences.
    
    This function tries multiple matching strategies:
    1. Direct match (exact)
    2. Normalized match (remove leading zeros) - tries normalized version directly
    3. Zero-padded match (add leading zeros to 4 digits)
    4. Iterate through all employees for normalized match (fallback)
    
    Args:
        empcode: Employee code from API (may have leading zeros like "0021")
        
    Returns:
        Employee object or None if not found
    """
    from ..models.employee import Employee
    
    if not empcode:
        return None
    
    empcode_str = str(empcode).strip()
    normalized_empcode = normalize_empcode(empcode_str)
    
    # Strategy 1: Direct match (exact)
    # This handles cases where DB has "0021" and API sends "0021"
    employee = Employee.objects.filter(empcode=empcode_str).first()
    if employee:
        logger.debug(f"Found employee with direct match: {empcode_str} -> {employee.empcode}")
        return employee
    
    # Strategy 2: Try normalized empcode directly (most common case)
    # This handles: API "0021" -> normalized "21" -> DB "21"
    if normalized_empcode != empcode_str:
        employee = Employee.objects.filter(empcode=normalized_empcode).first()
        if employee:
            logger.debug(f"Found employee with normalized match: {empcode_str} -> {normalized_empcode} -> {employee.empcode}")
            return employee
    
    # Strategy 3: Try zero-padded versions (pad to 4 digits)
    # This handles cases where API has "21" but DB has "0021"
    padded_empcode = empcode_str.zfill(4)
    if padded_empcode != empcode_str:
        employee = Employee.objects.filter(empcode=padded_empcode).first()
        if employee:
            logger.debug(f"Found employee with padded match: {empcode_str} -> {padded_empcode} -> {employee.empcode}")
            return employee
    
    # Strategy 4: Iterate through employees and compare normalized empcodes
    # This is a fallback for edge cases where normalization is needed on DB side
    # Example: DB has "00021" (5 digits) and API has "0021" (4 digits)
    all_employees = Employee.objects.all()
    for emp in all_employees:
        emp_normalized = normalize_empcode(emp.empcode)
        if emp_normalized == normalized_empcode:
            logger.debug(f"Found employee with normalized iteration match: {empcode_str} -> {normalized_empcode} == {emp.empcode} -> {emp_normalized}")
            return emp
    
    logger.warning(f"Employee not found for empcode: {empcode_str} (normalized: {normalized_empcode})")
    return None

# Use a fixed no-reply sender address for all outgoing emails
# Priority: 1. DEFAULT_FROM_EMAIL from settings/env, 2. Hardcoded fallback
def get_no_reply_email():
    """Get the no-reply email address from settings or use default"""
    # Try to get from settings (which reads from env file)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    if from_email:
        return from_email
    # Fallback to hardcoded value
    return 'no@reply.com'


def send_punch_reminder_email(employee_email, employee_name, empcode, last_punch_time, punch_type):
    """
    Send email reminder when employee forgets to punch after going out
    
    Args:
        employee_email: Employee email address
        employee_name: Employee name
        empcode: Employee code
        last_punch_time: Last punch time
        punch_type: Type of punch (IN/OUT)
    """
    try:
        subject = f"Punch Reminder - {employee_name} ({empcode})"
        
        message = f"""
Dear {employee_name},

This is a reminder that you have not made a punch after your last {punch_type} punch at {last_punch_time}.

Please ensure you make your punch entry to record your attendance properly.

If you are still outside the office, please ignore this message.

Best regards,
ORANGEDATATECH Pvt Ltd
        """
        
        # Use EmailMessage for better control over sender
        # Format: "Display Name <email@address.com>"
        no_reply_email = get_no_reply_email()
        email = EmailMessage(
            subject=subject,
            body=strip_tags(message),
            from_email=f"ORANGEDATATECH Pvt Ltd <{no_reply_email}>",
            to=[employee_email],
            reply_to=[no_reply_email],  # Set reply-to to no-reply
        )
        # Ensure the From header is set correctly
        email.extra_headers['From'] = f"ORANGEDATATECH Pvt Ltd <{no_reply_email}>"
        email.send(fail_silently=False)
        
        logger.info(f"Punch reminder email sent to {employee_email} for employee {empcode}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending punch reminder email to {employee_email}: {str(e)}")
        return False


def send_invalid_punch_email(employee_email, employee_name, empcode, punch_details):
    """
    Send email notification for invalid punch pattern
    
    Args:
        employee_email: Employee email address
        employee_name: Employee name
        empcode: Employee code
        punch_details: List of punch details that are invalid
    """
    try:
        subject = f"Invalid Punch Entry - {employee_name} ({empcode})"
        
        punch_info = "\n".join([
            f"  - Date: {punch.get('punch_date', 'N/A')}, "
            f"Time: {punch.get('punch_time', 'N/A')}, "
            f"MCID: {punch.get('mcid', 'N/A')}"
            for punch in punch_details
        ])
        
        message = f"""
Dear {employee_name},

This is to inform you that you have made an invalid punch entry. 

The punch pattern should alternate between IN (MCID=2) and OUT (MCID=1).
You cannot have consecutive punches with the same MCID value.

Invalid Punch Details:
{punch_info}

Please contact HR if you believe this is an error.

Best regards,
ORANGEDATATECH Pvt Ltd
        """
        
        # Use EmailMessage for better control over sender
        # Format: "Display Name <email@address.com>"
        no_reply_email = get_no_reply_email()
        email = EmailMessage(
            subject=subject,
            body=strip_tags(message),
            from_email=f"ORANGEDATATECH Pvt Ltd <{no_reply_email}>",
            to=[employee_email],
            reply_to=[no_reply_email],  # Set reply-to to no-reply
        )
        # Ensure the From header is set correctly
        email.extra_headers['From'] = f"ORANGEDATATECH Pvt Ltd <{no_reply_email}>"
        email.send(fail_silently=False)
        
        logger.info(f"Invalid punch email sent to {employee_email} for employee {empcode}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending invalid punch email to {employee_email}: {str(e)}")
        return False


def send_attendance_email(employee_email, employee_name, empcode, from_date, to_date, attendance_data, custom_message=None):
    """
    Send attendance report email to employee
    
    Args:
        employee_email: Employee email address
        employee_name: Employee name
        empcode: Employee code
        from_date: Start date of attendance period
        to_date: End date of attendance period
        attendance_data: List of attendance records, each containing:
            - date: Date of attendance
            - in_time: Check-in time
            - out_time: Check-out time
            - work_time: Total work time
            - over_time: Overtime hours
            - break_time: Break time
            - status: Attendance status
            - remark: Any remarks
            - late_in: Late arrival time
            - erl_out: Early departure time
        custom_message: Optional custom message to include after the period line
    """
    try:
        subject = f"Attendance Report - {employee_name} ({empcode}) - {from_date} to {to_date}"
        
        # Log the first record to debug what keys are being sent
        if attendance_data:
            logger.info(f"Sample attendance record keys: {list(attendance_data[0].keys())}")
            logger.info(f"Sample attendance record: {attendance_data[0]}")
        
        # Build HTML table for attendance data
        table_rows = ""
        for record in attendance_data:
            # Try multiple possible key names for each field
            date = record.get('date') or record.get('date_string') or record.get('Date') or ''
            in_time = record.get('in_time') or record.get('inTime') or record.get('In Time') or ''
            out_time = record.get('out_time') or record.get('outTime') or record.get('Out Time') or ''
            work_time = record.get('work_time') or record.get('workTime') or record.get('Work Time') or ''
            over_time = record.get('over_time') or record.get('overTime') or record.get('Overtime') or ''
            break_time = record.get('break_time') or record.get('breakTime') or record.get('Break Time') or ''
            status = record.get('status') or record.get('Status') or ''
            remark = record.get('remark') or record.get('Remark') or ''
            
            # Use empty string or '-' instead of 'N/A' for better readability
            date = date if date else '-'
            in_time = in_time if in_time else '-'
            out_time = out_time if out_time else '-'
            work_time = work_time if work_time else '-'
            over_time = over_time if over_time else '-'
            break_time = break_time if break_time else '-'
            status = status if status else '-'
            remark = remark if remark else '-'
            
            table_rows += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">{date}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{in_time}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{out_time}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{work_time}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{over_time}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{break_time}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{status}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">{remark}</td>
            </tr>
            """
        
        # Build custom message section if provided
        custom_message_html = ""
        if custom_message and custom_message.strip():
            custom_message_html = f"""
            <p style="margin: 15px 0; line-height: 1.6;">
                {custom_message.strip().replace(chr(10), '<br>')}
            </p>
            """
        
        # Create HTML email body
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    font-size: 14px;
                }}
                th {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 12px;
                    text-align: left;
                    border: 1px solid #ddd;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #ddd;
                }}
                tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <p>Dear {employee_name},</p>
                
                <p>Please find your attendance report for the period from <strong>{from_date}</strong> to <strong>{to_date}</strong>.</p>
                
                {custom_message_html}
                
                <p><strong>Employee Code:</strong> {empcode}<br>
                <strong>Employee Name:</strong> {employee_name}<br>
                <strong>Period:</strong> {from_date} to {to_date}</p>
                
                <h3 style="margin-top: 25px; margin-bottom: 15px;">Attendance Details:</h3>
                
                <table>
                    <thead>
                        <tr>
                            <th style="text-align: left;">Date</th>
                            <th style="text-align: center;">In Time</th>
                            <th style="text-align: center;">Out Time</th>
                            <th style="text-align: center;">Work Time</th>
                            <th style="text-align: center;">Overtime</th>
                            <th style="text-align: center;">Break</th>
                            <th style="text-align: center;">Status</th>
                            <th style="text-align: left;">Remarks</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
                
                <p style="margin-top: 25px;">If you have any questions or concerns regarding this attendance report, please contact HR.</p>
                
                <p style="margin-top: 20px;">Best regards,<br>
                <strong>ORANGEDATATECH Pvt Ltd</strong></p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version for email clients that don't support HTML
        plain_message = f"""
Dear {employee_name},

Please find your attendance report for the period from {from_date} to {to_date}.
"""
        if custom_message and custom_message.strip():
            plain_message += f"\n{custom_message.strip()}\n"
        
        plain_message += f"""
Employee Code: {empcode}
Employee Name: {employee_name}
Period: {from_date} to {to_date}

Attendance Details:
Date       | In Time | Out Time | Work Time | Overtime | Break | Status | Remarks
"""
        for record in attendance_data:
            date = record.get('date') or record.get('date_string') or record.get('Date') or '-'
            in_time = record.get('in_time') or record.get('inTime') or record.get('In Time') or '-'
            out_time = record.get('out_time') or record.get('outTime') or record.get('Out Time') or '-'
            work_time = record.get('work_time') or record.get('workTime') or record.get('Work Time') or '-'
            over_time = record.get('over_time') or record.get('overTime') or record.get('Overtime') or '-'
            break_time = record.get('break_time') or record.get('breakTime') or record.get('Break Time') or '-'
            status = record.get('status') or record.get('Status') or '-'
            remark = record.get('remark') or record.get('Remark') or '-'
            plain_message += f"{date:<10} | {in_time:<7} | {out_time:<8} | {work_time:<9} | {over_time:<8} | {break_time:<5} | {status:<6} | {remark}\n"
        
        plain_message += "\nIf you have any questions or concerns regarding this attendance report, please contact HR.\n\nBest regards,\nORANGEDATATECH Pvt Ltd"
        
        # Use EmailMessage for better control over sender
        # Format: "Display Name <email@address.com>"
        no_reply_email = get_no_reply_email()
        email = EmailMessage(
            subject=subject,
            body=plain_message,
            from_email=f"ORANGEDATATECH Pvt Ltd <{no_reply_email}>",
            to=[employee_email],
            reply_to=[no_reply_email],  # Set reply-to to no-reply
        )
        # Set HTML content
        email.content_subtype = "html"
        email.body = html_message
        # Ensure the From header is set correctly
        email.extra_headers['From'] = f"ORANGEDATATECH Pvt Ltd <{no_reply_email}>"
        email.send(fail_silently=False)
        
        logger.info(f"Attendance email sent to {employee_email} for employee {empcode} (Period: {from_date} to {to_date})")
        return True
        
    except Exception as e:
        logger.error(f"Error sending attendance email to {employee_email}: {str(e)}")
        return False
