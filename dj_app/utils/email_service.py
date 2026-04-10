"""
Email service utility for sending punch-related notifications
"""
import logging

logger = logging.getLogger(__name__)

EMAIL_FUNCTIONALITY_ENABLED = False


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
    # Email is disabled; keep a deterministic fallback.
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
    if not EMAIL_FUNCTIONALITY_ENABLED:
        logger.info(
            "Email disabled: skipping punch reminder email "
            f"(to={employee_email}, empcode={empcode}, punch_type={punch_type})"
        )
        return False

    # (Email sending intentionally disabled)
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
    if not EMAIL_FUNCTIONALITY_ENABLED:
        logger.info(
            "Email disabled: skipping invalid punch email "
            f"(to={employee_email}, empcode={empcode}, invalid_count={len(punch_details or [])})"
        )
        return False

    # (Email sending intentionally disabled)
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
    if not EMAIL_FUNCTIONALITY_ENABLED:
        logger.info(
            "Email disabled: skipping attendance report email "
            f"(to={employee_email}, empcode={empcode}, from={from_date}, to={to_date})"
        )
        return False

    # (Email sending intentionally disabled)
    return False
