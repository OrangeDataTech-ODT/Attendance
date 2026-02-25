"""
Punch monitoring views for validating punch data and sending notifications
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
import logging
import requests
import base64
import environ
import os
from django.conf import settings

from ..models.employee import Employee
from ..models.mcid import mcid
from ..models.email_log import EmailLog
from ..utils.email_service import send_punch_reminder_email, send_invalid_punch_email

logger = logging.getLogger(__name__)

# Initialize environment
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


class PunchMonitoringAPI(APIView):
    """
    API to monitor punch data for current day
    - Fetches data from FetchPunchData API for current day
    - Validates punch patterns (should alternate: 2,1,2,1...)
    - Sends email notifications for invalid punches
    - Sends email reminders if employee went out and didn't return within 30 minutes
    - Ignores sending emails after 7:00 PM
    """
    
    def get(self, request):
        """
        Main endpoint to trigger punch monitoring
        Can be called manually or scheduled to run every 30 minutes
        """
        try:
            # Get current date
            today = timezone.now().date()
            today_str = today.strftime('%d/%m/%Y')
            
            # Fetch punch data for current day
            punch_data = self._fetch_punch_data(today_str, today_str)
            
            if not punch_data:
                return Response({
                    "status": "success",
                    "message": "No punch data found for today",
                    "date": today_str
                }, status=status.HTTP_200_OK)
            
            # Process and validate punch data
            validation_results = self._validate_punch_patterns(punch_data, today_str)
            
            # Check for missing return punches
            reminder_results = self._check_missing_return_punches(punch_data, today_str)
            
            return Response({
                "status": "success",
                "date": today_str,
                "validation_results": validation_results,
                "reminder_results": reminder_results,
                "total_employees_checked": len(set([p.get('Empcode') for p in punch_data if p.get('Empcode')]))
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in punch monitoring: {str(e)}")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _fetch_punch_data(self, from_date, to_date):
        """
        Fetch punch data from the external API
        """
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
                # Handle different response formats
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
        """
        Validate punch patterns for all employees
        Expected pattern: First punch mcid=2, then alternating 1,2,1,2...
        Last punch should be mcid=1
        """
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
            
            # Parse punch date and time
            punch_datetime_str = punch.get('PunchDate', '')
            if not punch_datetime_str:
                continue
            
            try:
                # Parse date time (format: "dd/mm/yyyy HH:MM:SS")
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
            # Sort punches by datetime
            punches.sort(key=lambda x: x['datetime'])
            
            if len(punches) < 2:
                continue  # Need at least 2 punches to validate pattern
            
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
                
                # Check if consecutive punches have same mcid
                if prev_mcid == curr_mcid:
                    invalid_punches.append({
                        'punch': punches[i],
                        'reason': f"Consecutive punch with same MCID={curr_mcid}. Previous punch also had MCID={prev_mcid}"
                    })
                
                # Check pattern: should alternate (2->1, 1->2)
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
                        # Check if email already sent today for this employee
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
                                # Log the email
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
                        else:
                            logger.info(f"Invalid punch email already sent today for {empcode}")
                    else:
                        results["errors"].append({
                            'empcode': empcode,
                            'error': 'Employee not found or email not available'
                        })
                except Exception as e:
                    logger.error(f"Error sending invalid punch email for {empcode}: {str(e)}")
                    results["errors"].append({
                        'empcode': empcode,
                        'error': str(e)
                    })
        
        return results
    
    def _check_missing_return_punches(self, punch_data, date_str):
        """
        Check if employees who went out (mcid=1) haven't returned within 30 minutes
        Don't send emails after 7:00 PM
        """
        results = {
            "reminders_sent": 0,
            "employees_checked": 0,
            "errors": []
        }
        
        current_time = timezone.now()
        current_hour = current_time.hour
        
        # Don't send emails after 7:00 PM (19:00)
        if current_hour >= 19:
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
                
                # Track last punch for each employee
                if empcode not in employee_last_punch:
                    employee_last_punch[empcode] = {
                        'datetime': punch_datetime_tz,
                        'mcid': mcid_value,
                        'punch_date': punch.get('PunchDate', ''),
                        'punch_time': punch_datetime.strftime('%H:%M:%S'),
                        'name': punch.get('Name', '')
                    }
                else:
                    # Update if this punch is later
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
            
            # Only check if last punch was OUT (mcid=1)
            if last_punch['mcid'] != '1':
                continue
            
            # Check if 30 minutes have passed since last punch
            time_diff = current_time - last_punch['datetime']
            
            if time_diff >= timedelta(minutes=30):
                try:
                    # Use normalized empcode matching to handle zero-padding differences
                    from dj_app.utils.email_service import find_employee_by_empcode
                    employee = find_employee_by_empcode(empcode)
                    if employee and employee.email:
                        # Check if reminder email already sent today for this employee
                        today = timezone.now().date()
                        email_sent = EmailLog.objects.filter(
                            empcode=empcode,
                            email_type='punch_reminder',
                            date=today
                        ).exists()
                        
                        if not email_sent:
                            punch_type = "OUT"
                            if send_punch_reminder_email(
                                employee.email,
                                employee.name,
                                empcode,
                                last_punch['punch_time'],
                                punch_type
                            ):
                                # Log the email
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
                        else:
                            logger.info(f"Punch reminder email already sent today for {empcode}")
                    else:
                        results["errors"].append({
                            'empcode': empcode,
                            'error': 'Employee not found or email not available'
                        })
                except Exception as e:
                    logger.error(f"Error sending reminder email for {empcode}: {str(e)}")
                    results["errors"].append({
                        'empcode': empcode,
                        'error': str(e)
                    })
        
        return results
