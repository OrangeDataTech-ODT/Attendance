"""
Management command to monitor punch data and send notifications
Can be scheduled to run every 30 minutes using cron or task scheduler

Usage:
    python manage.py monitor_punches

For scheduling (Linux/Mac with cron):
    */30 * * * * cd /path/to/project && python manage.py monitor_punches

For scheduling (Windows with Task Scheduler):
    Create a task that runs every 30 minutes and executes:
    python manage.py monitor_punches
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import requests
import base64
import environ
import os
from django.conf import settings
import logging

from dj_app.models.employee import Employee
from dj_app.models.email_log import EmailLog
from dj_app.utils.email_service import send_punch_reminder_email, send_invalid_punch_email

logger = logging.getLogger(__name__)

# Initialize environment
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


class Command(BaseCommand):
    help = 'Monitor punch data for current day and send email notifications'

    def handle(self, *args, **options):
        self.stdout.write('Starting punch monitoring...')
        
        try:
            # Get current date
            today = timezone.now().date()
            today_str = today.strftime('%d/%m/%Y')
            
            self.stdout.write(f'Fetching punch data for {today_str}...')
            
            # Fetch punch data for current day
            punch_data = self._fetch_punch_data(today_str, today_str)
            
            if not punch_data:
                self.stdout.write(self.style.WARNING('No punch data found for today'))
                return
            
            self.stdout.write(f'Found {len(punch_data)} punch records')
            
            # Process and validate punch data
            self.stdout.write('Validating punch patterns...')
            validation_results = self._validate_punch_patterns(punch_data, today_str)
            
            # Check for missing return punches
            self.stdout.write('Checking for missing return punches...')
            reminder_results = self._check_missing_return_punches(punch_data, today_str)
            
            # Summary
            self.stdout.write(self.style.SUCCESS('\n=== Monitoring Summary ==='))
            self.stdout.write(f'Invalid punches found: {len(validation_results["invalid_punches"])}')
            self.stdout.write(f'Invalid punch emails sent: {validation_results["emails_sent"]}')
            self.stdout.write(f'Reminder emails sent: {reminder_results["reminders_sent"]}')
            self.stdout.write(f'Total employees checked: {reminder_results["employees_checked"]}')
            
            # Show debug info if available
            if "debug_info" in reminder_results:
                debug = reminder_results["debug_info"]
                self.stdout.write(f'\n--- Reminder Debug Details ---')
                self.stdout.write(f'Employees with OUT punch: {debug.get("employees_with_out_punch", 0)}')
                self.stdout.write(f'Eligible for reminder (>30 min): {debug.get("employees_eligible_for_reminder", 0)}')
                self.stdout.write(f'Already notified today: {debug.get("employees_already_notified", 0)}')
                self.stdout.write(f'No email/not found: {debug.get("employees_no_email", 0)}')
                self.stdout.write(f'Time too short (<30 min): {debug.get("employees_time_too_short", 0)}')
                self.stdout.write(f'Email send failures: {debug.get("email_send_failures", 0)}')
            
            if validation_results["errors"]:
                self.stdout.write(self.style.WARNING(f'Errors: {len(validation_results["errors"])}'))
            
            if reminder_results["errors"]:
                self.stdout.write(self.style.WARNING(f'Reminder errors: {len(reminder_results["errors"])}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in punch monitoring: {str(e)}'))
            logger.error(f"Error in punch monitoring command: {str(e)}")
            raise
    
    def _fetch_punch_data(self, from_date, to_date):
        """Fetch punch data from the external API"""
        try:
            api_url = (
                f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
                f"?Empcode=ALL&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
            )
            api_key = env('API_KEY_VALUE')
            base64_api_key = base64.b64encode(api_key.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {base64_api_key}",
                "Content-Type": "application/json",
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'PunchData' in data:
                    return data['PunchData']
                elif isinstance(data, list):
                    return data
                else:
                    return []
            else:
                logger.error(f"API returned status {response.status_code}: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching punch data: {str(e)}")
            return []
    
    def _validate_punch_patterns(self, punch_data, date_str):
        """Validate punch patterns for all employees"""
        results = {
            "invalid_punches": [],
            "emails_sent": 0,
            "errors": []
        }
        
        # Group punches by employee
        employee_punches = {}
        for punch in punch_data:
            empcode = punch.get('Empcode')
            if not empcode:
                continue
                
            if empcode not in employee_punches:
                employee_punches[empcode] = []
            
            punch_datetime_str = punch.get('PunchDate', '')
            if not punch_datetime_str:
                continue
            
            try:
                punch_datetime = datetime.strptime(punch_datetime_str, '%d/%m/%Y %H:%M:%S')
                mcid_value = str(punch.get('mcid', '')).strip()
                
                employee_punches[empcode].append({
                    'datetime': punch_datetime,
                    'mcid': mcid_value,
                    'punch_date': punch.get('PunchDate', ''),
                    'punch_time': punch_datetime.strftime('%H:%M:%S'),
                    'name': punch.get('Name', ''),
                    'raw_data': punch
                })
            except Exception as e:
                logger.warning(f"Error parsing punch datetime for {empcode}: {str(e)}")
                continue
        
        # Validate each employee's punches
        for empcode, punches in employee_punches.items():
            punches.sort(key=lambda x: x['datetime'])
            
            if len(punches) < 2:
                continue
            
            invalid_punches = []
            
            # Check first punch - should be mcid=2 (IN)
            if punches[0]['mcid'] != '2':
                invalid_punches.append({
                    'punch': punches[0],
                    'reason': f"First punch should be MCID=2 (IN), but got MCID={punches[0]['mcid']}"
                })
            
            # Check for consecutive same mcid values
            for i in range(1, len(punches)):
                prev_mcid = punches[i-1]['mcid']
                curr_mcid = punches[i]['mcid']
                
                if prev_mcid == curr_mcid:
                    invalid_punches.append({
                        'punch': punches[i],
                        'reason': f"Consecutive punch with same MCID={curr_mcid}"
                    })
                
                if prev_mcid == '2' and curr_mcid != '1':
                    invalid_punches.append({
                        'punch': punches[i],
                        'reason': f"After MCID=2 (IN), expected MCID=1 (OUT), but got MCID={curr_mcid}"
                    })
                elif prev_mcid == '1' and curr_mcid != '2':
                    invalid_punches.append({
                        'punch': punches[i],
                        'reason': f"After MCID=1 (OUT), expected MCID=2 (IN), but got MCID={curr_mcid}"
                    })
            
            # Check last punch - should be mcid=1 (OUT)
            if len(punches) > 0 and punches[-1]['mcid'] != '1':
                invalid_punches.append({
                    'punch': punches[-1],
                    'reason': f"Last punch should be MCID=1 (OUT), but got MCID={punches[-1]['mcid']}"
                })
            
            # Send email if invalid punches found
            if invalid_punches:
                try:
                    # Use normalized empcode matching to handle zero-padding differences
                    from dj_app.utils.email_service import find_employee_by_empcode
                    employee = find_employee_by_empcode(empcode)
                    if employee and employee.email:
                        today = timezone.now().date()
                        email_sent = EmailLog.objects.filter(
                            empcode=empcode,
                            email_type='invalid_punch',
                            date=today
                        ).exists()
                        
                        if not email_sent:
                            punch_details = [{
                                'punch_date': inv['punch']['punch_date'],
                                'punch_time': inv['punch']['punch_time'],
                                'mcid': inv['punch']['mcid'],
                                'reason': inv['reason']
                            } for inv in invalid_punches]
                            
                            if send_invalid_punch_email(
                                employee.email,
                                employee.name,
                                empcode,
                                punch_details
                            ):
                                EmailLog.objects.create(
                                    empcode=empcode,
                                    email_type='invalid_punch',
                                    date=today,
                                    details={'invalid_count': len(invalid_punches), 'punches': punch_details}
                                )
                                results["emails_sent"] += 1
                                results["invalid_punches"].append({
                                    'empcode': empcode,
                                    'name': employee.name,
                                    'invalid_count': len(invalid_punches),
                                    'punches': punch_details
                                })
                except Exception as e:
                    logger.error(f"Error sending invalid punch email for {empcode}: {str(e)}")
                    results["errors"].append({
                        'empcode': empcode,
                        'error': str(e)
                    })
        
        return results
    
    def _check_missing_return_punches(self, punch_data, date_str):
        """Check if employees who went out haven't returned within 30 minutes"""
        results = {
            "reminders_sent": 0,
            "employees_checked": 0,
            "errors": [],
            "debug_info": {
                "employees_with_out_punch": 0,
                "employees_eligible_for_reminder": 0,
                "employees_already_notified": 0,
                "employees_no_email": 0,
                "employees_time_too_short": 0,
                "email_send_failures": 0
            }
        }
        
        current_time = timezone.now()
        current_hour = current_time.hour
        
        # Don't send emails after 7:00 PM (19:00)
        if current_hour >= 19:
            self.stdout.write(self.style.WARNING(f'Email sending disabled after 7:00 PM (current hour: {current_hour})'))
            return {
                **results,
                "message": "Email sending disabled after 7:00 PM"
            }
        
        # Group punches by employee and get last punch
        employee_last_punch = {}
        for punch in punch_data:
            empcode = punch.get('Empcode')
            if not empcode:
                continue
            
            mcid_value = str(punch.get('mcid', '')).strip()
            punch_datetime_str = punch.get('PunchDate', '')
            
            if not punch_datetime_str:
                continue
            
            try:
                punch_datetime = datetime.strptime(punch_datetime_str, '%d/%m/%Y %H:%M:%S')
                punch_datetime_tz = timezone.make_aware(punch_datetime)
                
                if empcode not in employee_last_punch:
                    employee_last_punch[empcode] = {
                        'datetime': punch_datetime_tz,
                        'mcid': mcid_value,
                        'punch_date': punch.get('PunchDate', ''),
                        'punch_time': punch_datetime.strftime('%H:%M:%S'),
                        'name': punch.get('Name', '')
                    }
                else:
                    if punch_datetime_tz > employee_last_punch[empcode]['datetime']:
                        employee_last_punch[empcode] = {
                            'datetime': punch_datetime_tz,
                            'mcid': mcid_value,
                            'punch_date': punch.get('PunchDate', ''),
                            'punch_time': punch_datetime.strftime('%H:%M:%S'),
                            'name': punch.get('Name', '')
                        }
            except Exception as e:
                logger.warning(f"Error parsing punch datetime for {empcode}: {str(e)}")
                continue
        
        # Check employees who went out (mcid=1) and haven't returned
        for empcode, last_punch in employee_last_punch.items():
            results["employees_checked"] += 1
            
            if last_punch['mcid'] != '1':
                continue
            
            results["debug_info"]["employees_with_out_punch"] += 1
            
            time_diff = current_time - last_punch['datetime']
            time_diff_minutes = time_diff.total_seconds() / 60
            
            if time_diff < timedelta(minutes=30):
                results["debug_info"]["employees_time_too_short"] += 1
                logger.debug(f"Employee {empcode}: Time difference {time_diff_minutes:.1f} minutes < 30 minutes")
                continue
            
            results["debug_info"]["employees_eligible_for_reminder"] += 1
            
            try:
                # Use normalized empcode matching to handle zero-padding differences
                from dj_app.utils.email_service import find_employee_by_empcode
                employee = find_employee_by_empcode(empcode)
                if not employee:
                    results["debug_info"]["employees_no_email"] += 1
                    logger.warning(f"Employee {empcode} not found in database")
                    continue
                
                if not employee.email:
                    results["debug_info"]["employees_no_email"] += 1
                    logger.warning(f"Employee {empcode} ({employee.name}) has no email address")
                    continue
                
                today = timezone.now().date()
                email_sent = EmailLog.objects.filter(
                    empcode=empcode,
                    email_type='punch_reminder',
                    date=today
                ).exists()
                
                if email_sent:
                    results["debug_info"]["employees_already_notified"] += 1
                    logger.debug(f"Reminder email already sent today for {empcode}")
                    continue
                
                punch_type = "OUT"
                logger.info(f"Attempting to send reminder email to {empcode} ({employee.name}) - Last OUT punch: {last_punch['punch_time']}, Time since: {time_diff_minutes:.1f} minutes")
                
                if send_punch_reminder_email(
                    employee.email,
                    employee.name,
                    empcode,
                    last_punch['punch_time'],
                    punch_type
                ):
                    EmailLog.objects.create(
                        empcode=empcode,
                        email_type='punch_reminder',
                        date=today,
                        details={
                            'last_punch_time': last_punch['punch_time'],
                            'punch_type': punch_type
                        }
                    )
                    results["reminders_sent"] += 1
                    logger.info(f"Successfully sent reminder email to {empcode}")
                else:
                    results["debug_info"]["email_send_failures"] += 1
                    logger.error(f"Failed to send reminder email to {empcode} - send_punch_reminder_email returned False")
            except Exception as e:
                logger.error(f"Error sending reminder email for {empcode}: {str(e)}")
                results["errors"].append({
                    'empcode': empcode,
                    'error': str(e)
                })
        
        return results

