from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
import base64
import environ
import os
import logging
from django.conf import settings
from datetime import datetime
from ..models.all_data import all_data

# Set up logger
logger = logging.getLogger(__name__)

# Initialize environment
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))

# Create your views here.

class FetchPunchData(APIView):
    """
    API view to fetch punch data for all employees
    Requires: from_date and to_date as query parameters
    Usage: /api/fetch-punch-data/?from_date=12/03/2025&to_date=15/03/2025
    """
    def get(self, request):
        # Get required parameters from query string
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Validate that required parameters are provided
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        api_url=(
            f"https://api.etimeoffice.com/api/DownloadInOutPunchData?Empcode=ALL&"
            f"FromDate={from_date}&ToDate={to_date}")
        # api_url = (
        #     f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
        #     f"?Empcode=ALL&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
        # )
        api_key = env('API_KEY_VALUE')
        
        # Encode the API key in base64
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                entry_dataALL = response.json()
                return Response(entry_dataALL, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": f"API returned status {response.status_code}", "details": response.text},
                    status=response.status_code
                )
        
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FetchPunchDataWithParams(APIView):
    """
    API view to fetch punch data with three variables: Empcode, FromDate, ToDate
    Requires: empcode, from_date, and to_date as query parameters
    Usage: /api/fetch-punch-data-params/?empcode=0010&from_date=12/03/2025&to_date=12/03/2025
    """
    def get(self, request):
        # Get required parameters from query string
        empcode = request.query_params.get('empcode')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Validate that all required parameters are provided
        if not empcode:
            return Response(
                {"error": "Missing required parameter: empcode"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build the API URL with the three variables
        api_url=(
            f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
            f"?Empcode={empcode}&FromDate={from_date}&ToDate={to_date}")
        # api_url = (
        #     f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
        #     f"?Empcode={empcode}&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
        # )
        
        api_key = env('API_KEY_VALUE')
        
        # Encode the API key in base64
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                entry_dataALL = response.json()
                return Response(entry_dataALL, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": f"API returned status {response.status_code}", "details": response.text},
                    status=response.status_code
                )
        
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FetchEmployeePunchData(APIView):
    """
    Unified API view to fetch punch data for employees with flexible employee selection
    Requires: from_date and to_date as query parameters
    Optional: empcode (single or comma-separated multiple employee codes)
    
    Usage Examples:
    - All employees: /api/fetch-employee-data/?from_date=12/03/2025&to_date=15/03/2025
    - Single employee: /api/fetch-employee-data/?empcode=0010&from_date=12/03/2025&to_date=12/03/2025
    - Multiple employees: /api/fetch-employee-data/?empcode=0010,0011,0012&from_date=12/03/2025&to_date=12/03/2025
    """
    def get(self, request):
        # Get required parameters from query string
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        empcode = request.query_params.get('empcode')
        
        # Validate that required parameters are provided
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get API key
        api_key = env('API_KEY_VALUE')
        
        # Encode the API key in base64
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            # If no empcode provided, fetch all employees
            if not empcode:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
                    f"?Empcode=ALL&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
                )
                response = requests.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    return Response(response.json(), status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"error": f"API returned status {response.status_code}", "details": response.text},
                        status=response.status_code
                    )
            
            # Parse empcode(s) - handle comma-separated values
            empcodes = [code.strip() for code in empcode.split(',') if code.strip()]
            
            if not empcodes:
                return Response(
                    {"error": "Invalid empcode parameter"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # If single employee, make one API call
            if len(empcodes) == 1:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
                    f"?Empcode={empcodes[0]}&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
                )
                response = requests.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    return Response(response.json(), status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"error": f"API returned status {response.status_code}", "details": response.text},
                        status=response.status_code
                    )
            
            # If multiple employees, make multiple API calls and combine results
            all_data = []
            errors = []
            successful_count = 0
            
            for emp_code in empcodes:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
                    f"?Empcode={emp_code}&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
                )
                
                try:
                    response = requests.get(api_url, headers=headers)
                    
                    if response.status_code == 200:
                        emp_data = response.json()
                        # If the response is a list, extend; if dict, append
                        if isinstance(emp_data, list):
                            all_data.extend(emp_data)
                        else:
                            all_data.append(emp_data)
                        successful_count += 1
                    else:
                        errors.append({
                            "empcode": emp_code,
                            "error": f"API returned status {response.status_code}",
                            "details": response.text
                        })
                except Exception as e:
                    errors.append({
                        "empcode": emp_code,
                        "error": "An error occurred",
                        "details": str(e)
                    })
            
            # Return combined results
            result = {
                "data": all_data,
                "total_employees_requested": len(empcodes),
                "successful_requests": successful_count,
            }
            
            if errors:
                result["errors"] = errors
            
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FetchInOutPunchDataAll(APIView):
    """
    API view to fetch InOut punch data for all employees
    Requires: from_date and to_date as query parameters
    Date format: DD/MM/YYYY (e.g., 03/03/2025)
    Usage: /api/inout-punch-data/all/?from_date=03/03/2025&to_date=05/03/2025
    """
    def get(self, request):
        # Get required parameters from query string
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Validate that required parameters are provided
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build API URL - format: DD/MM/YYYY
        api_url = (
            f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
            f"?Empcode=ALL&FromDate={from_date}&ToDate={to_date}"
        )
        
        api_key = env('API_KEY_VALUE')
        
        # Encode the API key in base64
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                entry_data = response.json()
                
                # Save data to all_data model (for scheduled tasks and /inout/list/ endpoint)
                logger.info(f"API response received, type: {type(entry_data)}")
                created_count, updated_count, skipped_count, save_errors = _save_to_all_data_model(entry_data)
                total_saved = created_count + updated_count
                logger.info(f"Save operation completed: {created_count} created, {updated_count} updated, {skipped_count} skipped, {len(save_errors)} errors")
                
                # Calculate total unique employees (all registered employees in the system)
                # This counts all unique empcodes regardless of whether they have intime or not
                # Total employees = all unique empcodes in the response (all registered employees)
                total_unique_employees = 0
                data_list = []
                
                if isinstance(entry_data, list):
                    data_list = entry_data
                elif isinstance(entry_data, dict):
                    # Check if it's a nested structure with 'data' key
                    if 'data' in entry_data and isinstance(entry_data['data'], list):
                        data_list = entry_data['data']
                    elif 'PunchData' in entry_data and isinstance(entry_data['PunchData'], list):
                        data_list = entry_data['PunchData']
                    else:
                        # Single record
                        data_list = [entry_data]
                
                # Extract all unique empcodes (all registered employees)
                unique_empcodes = set()
                for item in data_list:
                    if isinstance(item, dict):
                        empcode = item.get('Empcode') or item.get('empcode') or item.get('EmpCode')
                        if empcode:
                            unique_empcodes.add(str(empcode))
                
                total_unique_employees = len(unique_empcodes)
                
                # Return data with total employees count and save status
                if isinstance(entry_data, list):
                    response_data = {
                        "data": entry_data,
                        "total_employees": total_unique_employees,
                        "created_records": created_count,
                        "updated_records": updated_count,
                        "skipped_records": skipped_count,
                        "total_processed": created_count + updated_count + skipped_count,
                        "save_operation_status": "success" if (created_count + updated_count) > 0 else "no_records_saved"
                    }
                    if save_errors:
                        response_data["save_errors"] = save_errors
                        response_data["save_operation_status"] = "partial_success" if (created_count + updated_count) > 0 else "failed"
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    # If it's already a dict, add total_employees to it
                    if isinstance(entry_data, dict):
                        entry_data['total_employees'] = total_unique_employees
                        entry_data['created_records'] = created_count
                        entry_data['updated_records'] = updated_count
                        entry_data['skipped_records'] = skipped_count
                        entry_data['total_processed'] = created_count + updated_count + skipped_count
                        entry_data['save_operation_status'] = "success" if (created_count + updated_count) > 0 else "no_records_saved"
                        if save_errors:
                            entry_data['save_errors'] = save_errors
                            entry_data['save_operation_status'] = "partial_success" if (created_count + updated_count) > 0 else "failed"
                        # Ensure data is in the response
                        if 'data' not in entry_data and data_list:
                            entry_data['data'] = data_list
                    return Response(entry_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": f"API returned status {response.status_code}", "details": response.text},
                    status=response.status_code
                )
        
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FetchInOutPunchDataSelective(APIView):
    """
    API view to fetch InOut punch data for selective employees with date range
    Requires: empcode, from_date, and to_date as query parameters
    Date format: DD/MM/YYYY (e.g., 03/03/2025)
    Supports single or multiple employee codes (comma-separated)
    Usage: /api/inout-punch-data/selective/?empcode=0001&from_date=03/03/2025&to_date=05/03/2025
    Usage (multiple): /api/inout-punch-data/selective/?empcode=0001,0002,0003&from_date=03/03/2025&to_date=05/03/2025
    """
    def get(self, request):
        empcode = request.query_params.get('empcode')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        if not empcode:
            return Response(
                {"error": "Missing required parameter: empcode"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        api_key = env('API_KEY_VALUE')
        
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            empcodes = [code.strip() for code in empcode.split(',') if code.strip()]
            
            if not empcodes:
                return Response(
                    {"error": "Invalid empcode parameter"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(empcodes) == 1:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
                    f"?Empcode={empcodes[0]}&FromDate={from_date}&ToDate={to_date}"
                )
                response = requests.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    return Response(response.json(), status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"error": f"API returned status {response.status_code}", "details": response.text},
                        status=response.status_code
                    )
            
            # If multiple employees, make multiple API calls and combine results
            all_data = []
            errors = []
            successful_count = 0
            
            for emp_code in empcodes:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
                    f"?Empcode={emp_code}&FromDate={from_date}&ToDate={to_date}"
                )
                
                try:
                    response = requests.get(api_url, headers=headers)
                    
                    if response.status_code == 200:
                        emp_data = response.json()
                        # If the response is a list, extend; if dict, append
                        if isinstance(emp_data, list):
                            all_data.extend(emp_data)
                        else:
                            all_data.append(emp_data)
                        successful_count += 1
                    else:
                        errors.append({
                            "empcode": emp_code,
                            "error": f"API returned status {response.status_code}",
                            "details": response.text
                        })
                except Exception as e:
                    errors.append({
                        "empcode": emp_code,
                        "error": "An error occurred",
                        "details": str(e)
                    })
            
           
            result = {
                "data": all_data,
                "total_employees_requested": len(empcodes),
                "successful_requests": successful_count,
            }
            
            if errors:
                result["errors"] = errors
            
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def _save_to_all_data_model(api_response_data):
    """
    Helper function to save API response data to all_data model
    Updates existing records only if data has changed, otherwise skips update
    Creates new records if they don't exist
    Returns: (created_count, updated_count, skipped_count, errors)
    """
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []
    
    # Handle different response formats
    data_list = []
    if isinstance(api_response_data, list):
        data_list = api_response_data
    elif isinstance(api_response_data, dict):
        if 'data' in api_response_data and isinstance(api_response_data['data'], list):
            data_list = api_response_data['data']
        elif 'PunchData' in api_response_data and isinstance(api_response_data['PunchData'], list):
            data_list = api_response_data['PunchData']
        else:
            # Check if dict has keys that look like employee data
            # If it has Empcode or empcode, treat as single record
            if 'Empcode' in api_response_data or 'empcode' in api_response_data or 'EmpCode' in api_response_data:
                data_list = [api_response_data]
            else:
                # Try to find any list in the dict
                for key, value in api_response_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        data_list = value
                        break
    
    # Debug: Log the data structure
    logger.info(f"Processing {len(data_list)} records for saving")
    if len(data_list) > 0:
        logger.info(f"Sample record keys: {list(data_list[0].keys()) if isinstance(data_list[0], dict) else 'Not a dict'}")
    
    for item in data_list:
        try:
            if not isinstance(item, dict):
                continue
            
            # Extract fields from API response (handle different possible field names)
            empcode = str(item.get('Empcode') or item.get('empcode') or item.get('EmpCode') or '')
            if not empcode:
                continue
            
            # Parse date from DateString or Date field (format: DD/MM/YYYY or DD/MM/YYYY HH:MM:SS)
            date_string = item.get('DateString') or item.get('dateString') or item.get('Date') or item.get('date') or item.get('PunchDate') or ''
            date_obj = None
            if date_string:
                try:
                    # Try parsing DD/MM/YYYY format
                    if isinstance(date_string, str):
                        # Remove time part if present
                        date_part = date_string.split()[0] if ' ' in date_string else date_string
                        # Try DD/MM/YYYY format first
                        try:
                            date_obj = datetime.strptime(date_part, '%d/%m/%Y').date()
                        except ValueError:
                            # Try YYYY-MM-DD format
                            try:
                                date_obj = datetime.strptime(date_part, '%Y-%m-%d').date()
                            except ValueError:
                                # Try other common formats
                                try:
                                    date_obj = datetime.strptime(date_part, '%m/%d/%Y').date()
                                except ValueError:
                                    logger.warning(f"Could not parse date: {date_part}")
                                    continue
                    else:
                        # If it's already a date object
                        date_obj = date_string
                except Exception as e:
                    logger.warning(f"Error parsing date {date_string}: {str(e)}")
                    continue
            else:
                # If no date found, try to use from_date parameter or skip
                logger.warning(f"No date field found in item: {item.get('Empcode', 'Unknown')}")
                continue
            
            if not date_obj:
                continue
            
            # Map API response fields to model fields
            # Handle different possible field names in API response
            in_time_val = item.get('INTime') or item.get('inTime') or item.get('InTime') or item.get('IN_TIME') or ''
            in_time = str(in_time_val)[:10] if in_time_val else ''
            
            out_time_val = item.get('OUTTime') or item.get('outTime') or item.get('OutTime') or item.get('OUT_TIME') or ''
            out_time = str(out_time_val)[:10] if out_time_val else ''
            
            work_time_val = item.get('WorkTime') or item.get('workTime') or item.get('Work_Time') or item.get('WORK_TIME') or ''
            work_time = str(work_time_val)[:10] if work_time_val else ''
            
            over_time_val = item.get('OverTime') or item.get('overTime') or item.get('Over_Time') or item.get('OVER_TIME') or ''
            over_time = str(over_time_val)[:10] if over_time_val else ''
            
            break_time_val = item.get('BreakTime') or item.get('breakTime') or item.get('Break_Time') or item.get('BREAK_TIME') or ''
            break_time = str(break_time_val)[:10] if break_time_val else ''
            
            status_val_temp = item.get('Status') or item.get('status') or item.get('STATUS') or ''
            status_val = str(status_val_temp)[:10] if status_val_temp else ''
            
            remark_temp = item.get('Remark') or item.get('remark') or item.get('REMARK') or ''
            remark = str(remark_temp)[:100] if remark_temp else ''
            
            erl_out_temp = item.get('ErlOut') or item.get('erlOut') or item.get('Erl_Out') or item.get('ERL_OUT') or ''
            erl_out = str(erl_out_temp)[:10] if erl_out_temp else ''
            
            late_in_temp = item.get('Late_In') or item.get('late_in') or item.get('LateIn') or item.get('LATE_IN') or ''
            late_in = str(late_in_temp)[:10] if late_in_temp else ''
            
            name_temp = item.get('Name') or item.get('name') or item.get('EmployeeName') or item.get('employeeName') or ''
            name = str(name_temp)[:100] if name_temp else ''
            
            # Check if record already exists
            existing_record = all_data.objects.filter(
                empcode=empcode,
                date_string=date_obj
            ).first()
            
            # Prepare new data dictionary
            new_data = {
                'in_time': in_time,
                'out_time': out_time,
                'work_time': work_time,
                'over_time': over_time,
                'break_time': break_time,
                'status': status_val,
                'remark': remark,
                'erl_out': erl_out,
                'late_in': late_in,
                'name': name,
            }
            
            if existing_record:
                # Record exists - check if data has changed
                has_changes = (
                    existing_record.in_time != new_data['in_time'] or
                    existing_record.out_time != new_data['out_time'] or
                    existing_record.work_time != new_data['work_time'] or
                    existing_record.over_time != new_data['over_time'] or
                    existing_record.break_time != new_data['break_time'] or
                    existing_record.status != new_data['status'] or
                    existing_record.remark != new_data['remark'] or
                    existing_record.erl_out != new_data['erl_out'] or
                    existing_record.late_in != new_data['late_in'] or
                    existing_record.name != new_data['name']
                )
                
                if has_changes:
                    # Update only if there are changes
                    for key, value in new_data.items():
                        setattr(existing_record, key, value)
                    existing_record.save()
                    updated_count += 1
                    logger.debug(f"Updated record for empcode {empcode} on {date_obj}")
                else:
                    # No changes - skip update
                    skipped_count += 1
                    logger.debug(f"No changes for empcode {empcode} on {date_obj} - skipping update")
            else:
                # Record doesn't exist - create new
                all_data.objects.create(
                    empcode=empcode,
                    date_string=date_obj,
                    **new_data
                )
                created_count += 1
                logger.debug(f"Created new record for empcode {empcode} on {date_obj}")
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Error saving record: {error_msg}")
            errors.append({
                'item': str(item.get('Empcode', item.get('empcode', 'Unknown'))),
                'error': str(e)
            })
    
    total_processed = created_count + updated_count + skipped_count
    logger.info(f"Processed {total_processed} records: {created_count} created, {updated_count} updated, {skipped_count} skipped, {len(errors)} errors")
    return created_count, updated_count, skipped_count, errors


class FetchInOutPunchData(APIView):
    """
    Unified API view to fetch InOut punch data with flexible employee selection
    Requires: from_date and to_date as query parameters
    Optional: empcode (single or comma-separated multiple employee codes)
    Date format: DD/MM/YYYY (e.g., 03/03/2025)
    
    Usage Examples:
    - All employees: /api/inout-punch-data/?from_date=03/03/2025&to_date=05/03/2025
    - Single employee: /api/inout-punch-data/?empcode=0001&from_date=03/03/2025&to_date=03/03/2025
    - Multiple employees: /api/inout-punch-data/?empcode=0001,0002,0003&from_date=03/03/2025&to_date=05/03/2025
    """
    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        empcode = request.query_params.get('empcode')
        
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_key = env('API_KEY_VALUE')
        
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            if not empcode:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
                    f"?Empcode=ALL&FromDate={from_date}&ToDate={to_date}"
                )
                response = requests.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    api_data = response.json()
                    logger.info(f"API response received (all employees), type: {type(api_data)}")
                    # Do NOT save data to all_data model for /inout/search/ endpoint
                    # Prepare response
                    if isinstance(api_data, dict):
                        response_data = api_data.copy()
                    else:
                        response_data = {"data": api_data}
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"error": f"API returned status {response.status_code}", "details": response.text},
                        status=response.status_code
                    )
            
            empcodes = [code.strip() for code in empcode.split(',') if code.strip()]
            
            if not empcodes:
                return Response(
                    {"error": "Invalid empcode parameter"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(empcodes) == 1:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
                    f"?Empcode={empcodes[0]}&FromDate={from_date}&ToDate={to_date}"
                )
                response = requests.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    api_data = response.json()
                    logger.info(f"API response received (single empcode), type: {type(api_data)}")
                    # Do NOT save data to all_data model for /inout/search/ endpoint
                    # Prepare response
                    if isinstance(api_data, dict):
                        response_data = api_data.copy()
                    else:
                        response_data = {"data": api_data}
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"error": f"API returned status {response.status_code}", "details": response.text},
                        status=response.status_code
                    )
            
            all_data_list = []
            errors = []
            successful_count = 0
            
            for emp_code in empcodes:
                api_url = (
                    f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
                    f"?Empcode={emp_code}&FromDate={from_date}&ToDate={to_date}"
                )
                
                try:
                    response = requests.get(api_url, headers=headers)
                    
                    if response.status_code == 200:
                        emp_data = response.json()
                        if isinstance(emp_data, list):
                            all_data_list.extend(emp_data)
                        else:
                            all_data_list.append(emp_data)
                        successful_count += 1
                    else:
                        errors.append({
                            "empcode": emp_code,
                            "error": f"API returned status {response.status_code}",
                            "details": response.text
                        })
                except Exception as e:
                    errors.append({
                        "empcode": emp_code,
                        "error": "An error occurred",
                        "details": str(e)
                    })
            
            # Do NOT save data to all_data model for /inout/search/ endpoint
            
            result = {
                "data": all_data_list,
                "total_employees_requested": len(empcodes),
                "successful_requests": successful_count,
            }
            
            if errors:
                result["errors"] = errors
            
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FetchAndStorePunchDataAPI(APIView):
    """
    API endpoint to fetch punch data from external API with date range and store it to the database
    Requires: from_date and to_date as query parameters
    Date format: DD/MM/YYYY (e.g., 03/03/2025)
    
    Usage: GET /inout/fetch-and-store/?from_date=03/03/2025&to_date=05/03/2025
    
    This endpoint:
    1. Fetches data from external API (DownloadInOutPunchData)
    2. Saves/updates data to all_data table (punch_data_all)
    3. Returns summary of saved records
    """
    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Validate required parameters
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build API URL - format: DD/MM/YYYY
        api_url = (
            f"https://api.etimeoffice.com/api/DownloadInOutPunchData"
            f"?Empcode=ALL&FromDate={from_date}&ToDate={to_date}"
        )
        
        api_key = env('API_KEY_VALUE')
        
        # Encode the API key in base64
        base64_api_key = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            logger.info(f"Fetching punch data from external API: from_date={from_date}, to_date={to_date}")
            response = requests.get(api_url, headers=headers, timeout=60)
            
            if response.status_code == 200:
                entry_data = response.json()
                logger.info(f"API response received, type: {type(entry_data)}")
                
                # Save data to all_data model
                created_count, updated_count, skipped_count, save_errors = _save_to_all_data_model(entry_data)
                total_processed = created_count + updated_count + skipped_count
                logger.info(f"Save operation completed: {created_count} created, {updated_count} updated, {skipped_count} skipped, {len(save_errors)} errors")
                
                # Calculate total unique employees
                total_unique_employees = 0
                data_list = []
                
                if isinstance(entry_data, list):
                    data_list = entry_data
                elif isinstance(entry_data, dict):
                    if 'data' in entry_data and isinstance(entry_data['data'], list):
                        data_list = entry_data['data']
                    elif 'PunchData' in entry_data and isinstance(entry_data['PunchData'], list):
                        data_list = entry_data['PunchData']
                    else:
                        data_list = [entry_data]
                
                # Extract all unique empcodes
                unique_empcodes = set()
                for item in data_list:
                    if isinstance(item, dict):
                        empcode = item.get('Empcode') or item.get('empcode') or item.get('EmpCode')
                        if empcode:
                            unique_empcodes.add(str(empcode))
                
                total_unique_employees = len(unique_empcodes)
                
                # Return success response with summary
                response_data = {
                    "status": "success",
                    "message": f"Successfully fetched and stored punch data",
                    "from_date": from_date,
                    "to_date": to_date,
                    "total_employees": total_unique_employees,
                    "created_records": created_count,
                    "updated_records": updated_count,
                    "skipped_records": skipped_count,
                    "total_processed": total_processed,
                    "save_operation_status": "success" if (created_count + updated_count) > 0 else "no_records_saved"
                }
                
                if save_errors:
                    response_data["save_errors"] = save_errors[:10]  # Limit to first 10 errors
                    response_data["total_errors"] = len(save_errors)
                    response_data["save_operation_status"] = "partial_success" if (created_count + updated_count) > 0 else "failed"
                
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                logger.error(f"API returned status {response.status_code}: {response.text}")
                return Response(
                    {"error": f"API returned status {response.status_code}", "details": response.text},
                    status=response.status_code
                )
        
        except Exception as e:
            logger.error(f"Error in FetchAndStorePunchDataAPI: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RetrieveStoredPunchDataAPI(APIView):
    """
    API endpoint to retrieve stored punch data from the database (all_data table)
    Requires: from_date and to_date as query parameters
    Optional: empcode (single or comma-separated multiple employee codes)
    Date format: YYYY-MM-DD (e.g., 2025-03-03) or DD/MM/YYYY (e.g., 03/03/2025)
    
    Usage Examples:
    - All employees: GET /inout/retrieve/?from_date=2025-03-03&to_date=2025-03-05
    - Single employee: GET /inout/retrieve/?empcode=0001&from_date=2025-03-03&to_date=2025-03-05
    - Multiple employees: GET /inout/retrieve/?empcode=0001,0002,0003&from_date=2025-03-03&to_date=2025-03-05
    """
    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        empcode = request.query_params.get('empcode')
        
        # Validate required parameters
        if not from_date:
            return Response(
                {"error": "Missing required parameter: from_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not to_date:
            return Response(
                {"error": "Missing required parameter: to_date"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Parse date strings - support both YYYY-MM-DD and DD/MM/YYYY formats
            def parse_date(date_str):
                """Parse date string in multiple formats"""
                if not date_str:
                    return None
                
                date_str = date_str.strip()
                
                # Try YYYY-MM-DD format first
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
                
                # Try DD/MM/YYYY format
                try:
                    return datetime.strptime(date_str, '%d/%m/%Y').date()
                except ValueError:
                    pass
                
                # Try MM/DD/YYYY format
                try:
                    return datetime.strptime(date_str, '%m/%d/%Y').date()
                except ValueError:
                    pass
                
                raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD or DD/MM/YYYY")
            
            from_date_obj = parse_date(from_date)
            to_date_obj = parse_date(to_date)
            
            if not from_date_obj or not to_date_obj:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if from_date_obj > to_date_obj:
                return Response(
                    {"error": "from_date cannot be greater than to_date"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Build query
            queryset = all_data.objects.filter(
                date_string__gte=from_date_obj,
                date_string__lte=to_date_obj
            )
            
            # Filter by empcode if provided
            if empcode:
                empcodes = [code.strip() for code in empcode.split(',') if code.strip()]
                if empcodes:
                    queryset = queryset.filter(empcode__in=empcodes)
            
            # Order by date and empcode
            queryset = queryset.order_by('date_string', 'empcode')
            
            # Convert to list of dictionaries
            data_list = []
            for record in queryset:
                data_list.append({
                    'id': record.id,
                    'empcode': record.empcode,
                    'name': record.name,
                    'date_string': record.date_string.strftime('%Y-%m-%d'),
                    'in_time': record.in_time,
                    'out_time': record.out_time,
                    'work_time': record.work_time,
                    'over_time': record.over_time,
                    'break_time': record.break_time,
                    'status': record.status,
                    'remark': record.remark,
                    'erl_out': record.erl_out,
                    'late_in': record.late_in,
                    'created_at': record.created_at.isoformat() if record.created_at else None,
                    'updated_at': record.updated_at.isoformat() if record.updated_at else None,
                })
            
            # Get unique empcodes count
            unique_empcodes = queryset.values_list('empcode', flat=True).distinct().count()
            
            return Response({
                "status": "success",
                "from_date": from_date_obj.strftime('%Y-%m-%d'),
                "to_date": to_date_obj.strftime('%Y-%m-%d'),
                "total_records": len(data_list),
                "total_unique_employees": unique_empcodes,
                "empcode_filter": empcode if empcode else "all",
                "data": data_list
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in RetrieveStoredPunchDataAPI: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )