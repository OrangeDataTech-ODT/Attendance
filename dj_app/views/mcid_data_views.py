from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
import base64
import environ
import os
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import pandas as pd
from ..models.mcid import mcid
from ..models.operation_data_models import operational_data


"""Here the data contain the mcid will be directly stored in a table and
    then the data further used from the data for refining
"""
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))

def transform_punch_data(data):
    """
    Transform punch data by splitting PunchDate into PunchDate and PunchTime
    Input: {"PunchDate": "05/01/2026 21:07:00", ...}
    Output: {"PunchDate": "05/01/2026", "PunchTime": "21:07:00", ...}
    """
    if isinstance(data, list):
        return [transform_punch_data(item) for item in data]
    elif isinstance(data, dict):
        transformed = data.copy()
        if 'PunchDate' in transformed and transformed['PunchDate']:
            try:
                # Parse the date-time string (format: "05/01/2026 21:07:00")
                punch_datetime = transformed['PunchDate']
                if ' ' in punch_datetime:
                    date_part, time_part = punch_datetime.split(' ', 1)
                    transformed['PunchDate'] = date_part
                    transformed['PunchTime'] = time_part
                else:
                    # If no time part, set time to empty or default
                    transformed['PunchDate'] = punch_datetime
                    transformed['PunchTime'] = ""
            except Exception:
                # If parsing fails, keep original value
                transformed['PunchTime'] = ""
        else:
            transformed['PunchTime'] = ""
        return transformed
    return data


class FetchPunchData(APIView):
    """API to fetch the punch data with the mcid values, transform it, and store in database"""
    
    def _save_or_update_mcid_data(self, transformed_data):
        """
        Save mcid data in the database.
        If record exists (based on unique_together), skip it (do not update).
        If record doesn't exist, create new record.
        Handles duplicates within the same batch correctly.
        """
        saved_count = 0
        already_similar_count = 0
        errors = []
        duplicate_in_batch_count = 0
        duplicate_examples = []
        
        if not isinstance(transformed_data, list):
            transformed_data = [transformed_data]
        
        # Track records we've already processed in this batch to detect duplicates
        batch_processed = {}
        # Track incoming data duplicates (same record appearing multiple times in API response)
        incoming_duplicates = {}
        
        # First, get all existing records from database in one query for better performance
        # Build a set of existing record keys
        existing_keys = set()
        existing_records = mcid.objects.all().values_list('empcode', 'punch_date', 'punch_time', 'mcid')
        for record in existing_records:
            existing_keys.add(tuple(record))
        
        # First pass: detect duplicates in incoming data
        for idx, item in enumerate(transformed_data):
            try:
                empcode = item.get('Empcode', '')
                punch_date = item.get('PunchDate', '')
                punch_time = item.get('PunchTime', '')
                mcid_value = item.get('mcid', '')
                
                # Skip if any required field is empty
                if not empcode or not punch_date or not punch_time or not mcid_value:
                    continue
                
                # Create a unique key for this record
                record_key = (empcode, punch_date, punch_time, mcid_value)
                
                # Track duplicates in incoming data
                if record_key in incoming_duplicates:
                    incoming_duplicates[record_key].append(idx)
                else:
                    incoming_duplicates[record_key] = [idx]
            except Exception:
                pass
        
        # Collect duplicate examples (records that appear more than once in incoming data)
        for record_key, indices in incoming_duplicates.items():
            if len(indices) > 1:
                duplicate_in_batch_count += len(indices) - 1  # Count extra occurrences
                if len(duplicate_examples) < 5:  # Limit to 5 examples
                    example_item = transformed_data[indices[0]]
                    duplicate_examples.append({
                        "empcode": example_item.get('Empcode', ''),
                        "punch_date": example_item.get('PunchDate', ''),
                        "punch_time": example_item.get('PunchTime', ''),
                        "mcid": example_item.get('mcid', ''),
                        "name": example_item.get('Name', ''),
                        "occurrences_in_batch": len(indices),
                        "indices": indices[:3]  # Show first 3 indices
                    })
        
        # Second pass: process records for saving
        for item in transformed_data:
            try:
                empcode = item.get('Empcode', '')
                punch_date = item.get('PunchDate', '')
                punch_time = item.get('PunchTime', '')
                mcid_value = item.get('mcid', '')
                
                # Skip if any required field is empty
                if not empcode or not punch_date or not punch_time or not mcid_value:
                    continue
                
                # Create a unique key for this record
                record_key = (empcode, punch_date, punch_time, mcid_value)
                
                # Check if this record already exists in database
                if record_key in existing_keys:
                    # Only count as "already similar" if we haven't seen this exact record in this batch before
                    if record_key not in batch_processed:
                        already_similar_count += 1
                        batch_processed[record_key] = True
                else:
                    # Check if we've already processed this exact record in this batch (duplicate in same API call)
                    if record_key in batch_processed:
                        # This is a duplicate within the same batch, skip it
                        continue
                    
                    # Create new record only if it doesn't exist
                    try:
                        mcid.objects.create(
                            name=item.get('Name', ''),
                            empcode=empcode,
                            punch_date=punch_date,
                            punch_time=punch_time,
                            m_flag=item.get('M_Flag') if item.get('M_Flag') else None,
                            mcid=mcid_value
                        )
                        saved_count += 1
                        # Add to both sets to track it
                        existing_keys.add(record_key)
                        batch_processed[record_key] = True
                    except Exception as create_error:
                        # Handle unique constraint violation (race condition or duplicate)
                        if 'unique' in str(create_error).lower() or 'duplicate' in str(create_error).lower():
                            # Record was created between our check and create (race condition)
                            # or it's a duplicate we missed
                            if record_key not in batch_processed:
                                already_similar_count += 1
                                batch_processed[record_key] = True
                            existing_keys.add(record_key)
                        else:
                            raise create_error
            except Exception as e:
                errors.append({
                    "data": item,
                    "error": str(e)
                })
        
        return {
            "saved_count": saved_count,
            "already_similar_count": already_similar_count,
            "duplicate_in_batch_count": duplicate_in_batch_count,
            "duplicate_examples": duplicate_examples,
            "errors": errors
        }
    
    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
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
        
        try:
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                entry_dataALL = response.json()
                
                # Handle different response formats
                if isinstance(entry_dataALL, dict) and 'PunchData' in entry_dataALL:
                    raw_data = entry_dataALL['PunchData']
                elif isinstance(entry_dataALL, list):
                    raw_data = entry_dataALL
                else:
                    raw_data = entry_dataALL
                
                # Transform the data (split PunchDate into PunchDate and PunchTime)
                transformed_data = transform_punch_data(raw_data)
                
                # Ensure transformed_data is a list for calculations
                if not isinstance(transformed_data, list):
                    transformed_data = [transformed_data] if transformed_data else []
                
                # Calculate statistics
                total_count = len(transformed_data)
                
                # Get distinct employee count
                distinct_employees = set()
                date_range = {"from": None, "to": None}
                
                for item in transformed_data:
                    if isinstance(item, dict):
                        # Collect distinct employee codes
                        empcode = item.get('Empcode')
                        if empcode:
                            distinct_employees.add(empcode)
                        
                        # Extract date range from actual data
                        punch_date = item.get('PunchDate')
                        if punch_date:
                            try:
                                # Parse date in format "05/01/2026"
                                date_obj = datetime.strptime(punch_date, '%d/%m/%Y').date()
                                if date_range["from"] is None or date_obj < date_range["from"]:
                                    date_range["from"] = date_obj
                                if date_range["to"] is None or date_obj > date_range["to"]:
                                    date_range["to"] = date_obj
                            except Exception:
                                pass
                
                # Format date range for response
                date_range_formatted = {
                    "from_date": date_range["from"].strftime('%d/%m/%Y') if date_range["from"] else from_date,
                    "to_date": date_range["to"].strftime('%d/%m/%Y') if date_range["to"] else to_date
                }
                
                # Save or update data in database
                save_result = self._save_or_update_mcid_data(transformed_data)
                
                # Return transformed data along with statistics at the top
                return Response({
                    "saved_count": save_result["saved_count"],
                    "already_similar_count": save_result["already_similar_count"],
                    "duplicate_in_batch_count": save_result["duplicate_in_batch_count"],
                    "duplicate_examples": save_result["duplicate_examples"],
                    "count": total_count,
                    "distinct_employees": len(distinct_employees),
                    "date_range": date_range_formatted,
                    "data": transformed_data,
                    "errors": save_result["errors"]
                }, status=status.HTTP_200_OK)
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


class ProcessMCIDDataOperations(APIView):
    """
    API view to perform operations on punch data from mcid table
    Usage: GET /id_only/process/?from_date=DD/MM/YYYY&to_date=DD/MM/YYYY
    Optional: empcode=EMPCODE (to filter by specific employee)
    
    Operations performed (day-wise for each employee):
    1. For each employee per day:
       - First punch: mcid = "2" (earliest punch of the day with mcid=2)
       - Last punch: The last punch of the day for that employee (can be mcid=1 or mcid=2)
         * It is the last punch of the day for that specific employee
         * Mostly it will be mcid=1, but can be mcid=2
         * Not just the latest by time, but the actual last punch of the day for that employee
       - Total time = Last punch - First punch
    2. Between first and last punches:
       - Valid pattern: mcid alternates between "1" and "2" (1, 2, 1, 2...)
       - Remove punches that break this pattern
    3. Calculate:
       - Break time = sum of time differences between mcid "1" and "2" pairs
       - Work time = Total time - Break time
    """
    
    def get(self, request):
        try:
            from_date = request.query_params.get('from_date')
            to_date = request.query_params.get('to_date')
            empcode_filter = request.query_params.get('empcode', None)
            
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
            
            # Parse date strings to date objects for filtering
            try:
                from_date_obj = datetime.strptime(from_date, '%d/%m/%Y').date()
                to_date_obj = datetime.strptime(to_date, '%d/%m/%Y').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use DD/MM/YYYY"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Query data from mcid table
            queryset = mcid.objects.all()
            
            # Filter by date range (punch_date is stored as string "DD/MM/YYYY")
            # We need to filter records where punch_date string falls within range
            filtered_records = []
            for record in queryset:
                try:
                    record_date = datetime.strptime(record.punch_date, '%d/%m/%Y').date()
                    if from_date_obj <= record_date <= to_date_obj:
                        if empcode_filter is None or record.empcode == empcode_filter:
                            filtered_records.append(record)
                except (ValueError, AttributeError):
                    continue
            
            if not filtered_records:
                return Response({
                    "status": "success",
                    "message": "No data found for the specified date range",
                    "total_employees": 0,
                    "total_punches": 0,
                    "employees": []
                }, status=status.HTTP_200_OK)
            
            # Convert to DataFrame for processing
            df = self._convert_to_dataframe(filtered_records)
            
            # Perform operations
            result = self._process_punch_data(df)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _convert_to_dataframe(self, records):
        """
        Convert mcid model records to pandas DataFrame
        Combines punch_date and punch_time into PunchDate datetime
        """
        data = []
        for record in records:
            try:
                # Combine punch_date and punch_time to create datetime
                date_str = record.punch_date
                time_str = record.punch_time
                
                # Create datetime string
                if time_str:
                    datetime_str = f"{date_str} {time_str}"
                else:
                    datetime_str = f"{date_str} 00:00:00"
                
                data.append({
                    'Empcode': record.empcode,
                    'Name': record.name,
                    'PunchDate': datetime_str,
                    'mcid': record.mcid,
                    'M_Flag': record.m_flag
                })
            except Exception:
                continue
        
        df = pd.DataFrame(data)
        
        if df.empty:
            return df
        
        # Convert PunchDate to datetime
        df['PunchDate'] = pd.to_datetime(df['PunchDate'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        
        # Sort by Empcode and PunchDate
        df = df.sort_values(['Empcode', 'PunchDate']).reset_index(drop=True)
        
        return df
    
    def _convert_hours_to_hours_minutes(self, decimal_hours):
        """
        Convert decimal hours to hours and minutes format as string
        Returns: string in "hh:mm" format
        """
        if decimal_hours == 0:
            return "0:00"
        
        hours = int(decimal_hours)
        minutes = int(round((decimal_hours - hours) * 60))
        
        # Handle case where minutes round up to 60
        if minutes >= 60:
            hours += 1
            minutes = 0
        
        # Format as "hh:mm" with zero-padding for minutes
        return f"{hours}:{minutes:02d}"
    
    def _process_punch_data(self, df):
        """
        Process punch data according to the specified rules (day-wise)
        """
        try:
            if df.empty:
                return {
                    "status": "success",
                    "total_employees": 0,
                    "total_punches": 0,
                    "employees": []
                }
            
            # Extract date from PunchDate for day-wise grouping
            df['Date'] = df['PunchDate'].dt.date
            
            # Initialize result structures
            employee_results = []
            invalid_punches = []
            total_punches_all_employees = 0
            
            # Process each employee-day combination
            for (empcode, date), group_df in df.groupby(['Empcode', 'Date']):
                emp_df = group_df.copy().reset_index(drop=True)
                
                # Calculate total punches count for this employee-day
                total_punches_count = len(emp_df)
                
                # Find first punch (mcid = "2" or 2, earliest)
                first_punch_mask = emp_df['mcid'].astype(str).str.strip() == '2'
                first_punch_candidates = emp_df[first_punch_mask]
                if first_punch_candidates.empty:
                    first_punch_candidates = emp_df[emp_df['mcid'] == 2]
                
                if first_punch_candidates.empty:
                    # No valid first punch - all punches are invalid
                    invalid_emp_punches = emp_df.to_dict('records')
                    invalid_punches.extend(invalid_emp_punches)
                    
                    employee_name = ""
                    if 'Name' in emp_df.columns and len(emp_df) > 0:
                        employee_name = str(emp_df.iloc[0].get('Name', ''))
                    
                    in_time_str = None
                    out_time_str = None
                    if len(emp_df) > 0 and pd.notna(emp_df.iloc[0]['PunchDate']):
                        first_punch_date = emp_df.iloc[0]['PunchDate']
                        in_time_str = first_punch_date.strftime('%H:%M:%S') if pd.notna(first_punch_date) else None
                    
                    if len(emp_df) > 0 and pd.notna(emp_df.iloc[-1]['PunchDate']):
                        last_punch_date = emp_df.iloc[-1]['PunchDate']
                        out_time_str = last_punch_date.strftime('%H:%M:%S') if pd.notna(last_punch_date) else None
                    
                    total_punches_all_employees += total_punches_count
                    
                    employee_result = {
                        "empcode": str(empcode),
                        "name": employee_name,
                        "date": date.strftime('%Y-%m-%d') if date else None,
                        "in_time": in_time_str,
                        "out_time": out_time_str,
                        "total_time": "0:00",
                        "break_time": "0:00",
                        "work_time": "0:00",
                        "total_punches_count": total_punches_count,
                        "invalid_punches_count": len(invalid_emp_punches)
                    }
                    employee_results.append(employee_result)
                    
                    # Save/update to operational_data table
                    if date:
                        operational_data.objects.update_or_create(
                            empcode=str(empcode),
                            date=date,
                            defaults={
                                'name': employee_name,
                                'in_time': in_time_str,
                                'out_time': out_time_str,
                                'total_time': "0:00",
                                'break_time': "0:00",
                                'work_time': "0:00",
                                'total_punches_count': total_punches_count,
                                'invalid_punches_count': len(invalid_emp_punches)
                            }
                        )
                    continue
                
                first_punch = first_punch_candidates.iloc[0]
                first_punch_time = first_punch['PunchDate']
                
                # Find last punch of the day for this employee
                # Last punch = the last punch of the day for that employee (not just latest by time)
                # Since we're already grouped by (empcode, date), this is the last punch of that day for that employee
                # Last punch can be mcid=1 or mcid=2 (mostly mcid=1, but can be mcid=2)
                # It is always the last punch of the day for that specific employee
                last_punch = emp_df.iloc[-1]  # Last punch of the day for this employee (already sorted by PunchDate)
                last_punch_time = last_punch['PunchDate']
                last_punch_mcid = str(last_punch['mcid']).strip()
                
                # Get all punches between first and last (inclusive) for pattern validation
                between_punches = emp_df[
                    (emp_df['PunchDate'] >= first_punch_time) & 
                    (emp_df['PunchDate'] <= last_punch_time)
                ].copy().reset_index(drop=True)
                
                # Validate pattern and separate valid/invalid punches
                # Pattern validation rules:
                # 1. First punch (mcid=2) is always valid
                # 2. Last punch (any mcid - can be mcid=1 or mcid=2) is always valid
                # 3. Middle punches between first and last must follow alternating pattern: 1, 2, 1, 2...
                # 4. Only middle punches that break the 1,2 pattern are marked as invalid
                valid_punches, invalid_emp_punches = self._validate_mcid_pattern(
                    between_punches, first_punch_time, last_punch_time, last_punch_mcid
                )
                
                # Add invalid punches to the invalid list
                invalid_punches.extend(invalid_emp_punches)
                
                # Calculate total time using first and last valid punches
                total_time = (last_punch_time - first_punch_time).total_seconds() / 3600
                
                # Calculate break time from valid punches only
                break_time = self._calculate_break_time(valid_punches)
                
                # Calculate work time
                work_time = total_time - break_time
                
                # Get employee name
                employee_name = ""
                if 'Name' in emp_df.columns and len(emp_df) > 0:
                    employee_name = str(emp_df.iloc[0].get('Name', ''))
                
                # Convert decimal hours to hours and minutes format
                total_time_formatted = self._convert_hours_to_hours_minutes(total_time)
                break_time_formatted = self._convert_hours_to_hours_minutes(break_time)
                work_time_formatted = self._convert_hours_to_hours_minutes(work_time)
                
                # Extract IN_TIME and OUT_TIME
                in_time_str = first_punch_time.strftime('%H:%M:%S') if pd.notna(first_punch_time) else None
                out_time_str = last_punch_time.strftime('%H:%M:%S') if pd.notna(last_punch_time) else None
                
                total_punches_all_employees += total_punches_count
                
                # Format results
                employee_result = {
                    "empcode": str(empcode),
                    "name": employee_name,
                    "date": date.strftime('%Y-%m-%d') if date else None,
                    "in_time": in_time_str,
                    "out_time": out_time_str,
                    "total_time": total_time_formatted,
                    "break_time": break_time_formatted,
                    "work_time": work_time_formatted,
                    "total_punches_count": total_punches_count,
                    "invalid_punches_count": len(invalid_emp_punches)
                }
                
                employee_results.append(employee_result)
                
                # Save/update to operational_data table
                if date:
                    operational_data.objects.update_or_create(
                        empcode=str(empcode),
                        date=date,
                        defaults={
                            'name': employee_name,
                            'in_time': in_time_str,
                            'out_time': out_time_str,
                            'total_time': total_time_formatted,
                            'break_time': break_time_formatted,
                            'work_time': work_time_formatted,
                            'total_punches_count': total_punches_count,
                            'invalid_punches_count': len(invalid_emp_punches)
                        }
                    )
            
            return {
                "status": "success",
                "total_employees": len(employee_results),
                "total_punches": total_punches_all_employees,
                "employees": employee_results
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing punch data: {str(e)}"
            }
    
    def _validate_mcid_pattern(self, df, first_punch_time, last_punch_time, last_punch_mcid):
        """
        Validate that mcid pattern follows: first (mcid=2), then 1,2,1,2... until last
        
        Last punch definition:
        - It is the last punch of the day for that employee (not just latest by time)
        - Can be mcid=1 or mcid=2 (mostly mcid=1, but can be mcid=2)
        - The last punch of the day for that employee is always valid regardless of its mcid value
        
        Returns: (valid_punches_df, invalid_punches_list)
        """
        if df.empty:
            return pd.DataFrame(), []
        
        df = df.reset_index(drop=True)
        
        valid_indices = []
        invalid_punches = []
        
        # Find first punch index (mcid = "2")
        first_mask = df['PunchDate'] == first_punch_time
        first_indices = df[first_mask].index.tolist()
        if len(first_indices) > 0:
            first_idx = first_indices[0]
            valid_indices.append(first_idx)
        
        # Find last punch index - the last punch of the day for that employee
        # Last punch is always valid regardless of mcid (can be mcid=1 or mcid=2)
        # It is the last punch of the day for that specific employee
        last_mask = df['PunchDate'] == last_punch_time
        last_indices = df[last_mask].index.tolist()
        if len(last_indices) > 0:
            last_idx = last_indices[-1]
            # Last punch of the day for that employee is always valid (can be mcid=1 or mcid=2)
            valid_indices.append(last_idx)
        
        # Get punches strictly between first and last
        middle_mask = (df['PunchDate'] > first_punch_time) & (df['PunchDate'] < last_punch_time)
        middle_punches = df[middle_mask].copy()
        
        if not middle_punches.empty:
            expected_next = '1'
            
            for idx in middle_punches.index:
                current_mcid = str(middle_punches.loc[idx, 'mcid']).strip()
                
                if current_mcid == expected_next:
                    valid_indices.append(idx)
                    expected_next = '2' if current_mcid == '1' else '1'
                else:
                    invalid_punches.append(middle_punches.loc[idx].to_dict())
        
        # Sort valid indices to maintain chronological order
        valid_indices = sorted(set(valid_indices))
        valid_df = df.iloc[valid_indices].copy() if valid_indices else pd.DataFrame()
        valid_df = valid_df.sort_values('PunchDate').reset_index(drop=True)
        
        return valid_df, invalid_punches
    
    def _calculate_break_time(self, df):
        """
        Calculate break time from valid pattern punches
        Break time = sum of time differences between mcid "1" (out) and "2" (in) pairs
        """
        if df.empty or len(df) < 2:
            return 0.0
        
        break_time = 0.0
        
        # Find pairs where mcid goes from "1" to "2" (break: out then in)
        for i in range(len(df) - 1):
            current_mcid = str(df.iloc[i]['mcid']).strip()
            next_mcid = str(df.iloc[i + 1]['mcid']).strip()
            
            if current_mcid == '1' and next_mcid == '2':
                time_diff = (df.iloc[i + 1]['PunchDate'] - df.iloc[i]['PunchDate']).total_seconds() / 3600
                break_time += time_diff
        
        return break_time