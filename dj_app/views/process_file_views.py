from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
import base64
import environ
import os
from django.conf import settings
import pandas as pd
import numpy as np
from datetime import datetime
import json
from io import BytesIO
from ..models import PunchDataFile
from ..models.operation_data_models import operational_data
from django.utils import timezone

env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))

def convert_to_native_types(obj):
    """
    Recursively convert numpy/pandas types to native Python types for JSON serialization
    """
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_native_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_native_types(item) for item in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj




class GetAllPunchDataFiles(APIView):
    """
    API view to retrieve all stored punch data files
    Usage: GET /all_emp/files/
    Optional query parameters:
    - limit: Number of records to return (default: all)
    - offset: Number of records to skip (default: 0)
    """
    def get(self, request):
        try:
            # Get query parameters for pagination
            limit = request.query_params.get('limit', None)
            offset = int(request.query_params.get('offset', 0))
            
            # Get all files
            files = PunchDataFile.objects.all()
            total_count = files.count()
            
            # Apply pagination if limit is provided
            if limit:
                try:
                    limit = int(limit)
                    files = files[offset:offset + limit]
                except ValueError:
                    return Response(
                        {"error": "Invalid limit parameter. Must be an integer."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                files = files[offset:]
            
            # Serialize the files
            files_data = []
            for file in files:
                files_data.append({
                    "id": file.id,
                    "filename": file.filename,
                    "file_path": file.file_path,
                    "blob_url": file.blob_url,
                    "blob_name": file.blob_name,
                    "container_name": file.container_name,
                    "from_date": file.from_date,
                    "to_date": file.to_date,
                    "total_records": file.total_records,
                    "unique_employees": file.unique_employees,
                    "created_at": file.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    "updated_at": file.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return Response({
                "total_count": total_count,
                "returned_count": len(files_data),
                "offset": offset,
                "files": files_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetPunchDataFileById(APIView):
    """
    API view to retrieve a specific punch data file by ID
    Usage: GET /all_emp/file/<id>/
    Optional query parameter:
    - include_data: Set to 'true' to include the full punch data (default: false)
    """
    def get(self, request, file_id):
        try:
            file = PunchDataFile.objects.get(id=file_id)
            
            # Check if user wants to include full data
            include_data = request.query_params.get('include_data', 'false').lower() == 'true'
            
            response_data = {
                "id": file.id,
                "filename": file.filename,
                "file_path": file.file_path,
                "blob_url": file.blob_url,
                "blob_name": file.blob_name,
                "container_name": file.container_name,
                "from_date": file.from_date,
                "to_date": file.to_date,
                "total_records": file.total_records,
                "unique_employees": file.unique_employees,
                "created_at": file.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "updated_at": file.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except PunchDataFile.DoesNotExist:
            return Response(
                {"error": f"File with id {file_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProcessPunchDataOperations(APIView):
    """
    API view to perform operations on punch data from a stored file
    Usage: GET /all_emp/process/<file_id>/
    
    Operations performed:
    1. For each employee:
       - First punch: mcid = "2" (earliest punch of the day)
       - Last punch: mcid = "1" (latest punch of the day)
       - Total time = Last punch - First punch
    2. Between first and last punches:
       - Valid pattern: mcid alternates between "1" and "2" (1, 2, 1, 2...)
       - Remove punches that break this pattern
    3. Calculate:
       - Break time = sum of time differences between mcid "1" and "2" pairs
       - Work time = Total time - Break time
    """
    def get(self, request, file_id):
        try:
            # Get file from database
            try:
                file = PunchDataFile.objects.get(id=file_id)
            except PunchDataFile.DoesNotExist:
                return Response(
                    {"error": f"File with id {file_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Download CSV from blob storage
            blob_url = file.blob_url
            if not blob_url:
                return Response(
                    {"error": "Blob URL not found for this file"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                response = requests.get(blob_url, timeout=30)
                if response.status_code != 200:
                    return Response(
                        {"error": f"Failed to download file from blob storage. Status: {response.status_code}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Read CSV into DataFrame
                csv_data = BytesIO(response.content)
                df = pd.read_csv(csv_data)
            except Exception as e:
                return Response(
                    {"error": f"Error downloading or reading CSV file: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Perform operations
            result = self._process_punch_data(df)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": "An error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
        Process punch data according to the specified rules
        """
        try:
            # Convert PunchDate to datetime
            df['PunchDate'] = pd.to_datetime(df['PunchDate'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
            
            # Sort by Empcode and PunchDate
            df = df.sort_values(['Empcode', 'PunchDate']).reset_index(drop=True)
            
            # Initialize result structures
            employee_results = []
            invalid_punches = []
            total_punches_all_employees = 0
            
            # Process each employee
            for empcode in df['Empcode'].unique():
                emp_df = df[df['Empcode'] == empcode].copy().reset_index(drop=True)
                
                # Calculate total punches count for this employee (all punches)
                total_punches_count = len(emp_df)
                
                # Find first punch (mcid = "2" or 2, earliest)
                # Handle both string and numeric mcid values
                first_punch_mask = emp_df['mcid'].astype(str).str.strip() == '2'
                first_punch_candidates = emp_df[first_punch_mask]
                if first_punch_candidates.empty:
                    # Try numeric comparison as fallback
                    first_punch_candidates = emp_df[emp_df['mcid'] == 2]
                
                if first_punch_candidates.empty:
                    # No valid first punch - all punches are invalid
                    invalid_emp_punches = emp_df.to_dict('records')
                    invalid_punches.extend(invalid_emp_punches)
                    # Get employee name (try different possible column names)
                    employee_name = ""
                    if 'Name' in emp_df.columns and len(emp_df) > 0:
                        employee_name = str(emp_df.iloc[0].get('Name', ''))
                    elif 'name' in emp_df.columns and len(emp_df) > 0:
                        employee_name = str(emp_df.iloc[0].get('name', ''))
                    elif 'EmployeeName' in emp_df.columns and len(emp_df) > 0:
                        employee_name = str(emp_df.iloc[0].get('EmployeeName', ''))
                    
                    # Try to extract date from first available punch
                    date_value = None
                    in_time_str = None
                    out_time_str = None
                    if len(emp_df) > 0 and pd.notna(emp_df.iloc[0]['PunchDate']):
                        first_punch_date = emp_df.iloc[0]['PunchDate']
                        date_value = first_punch_date.date() if pd.notna(first_punch_date) else None
                        in_time_str = first_punch_date.strftime('%H:%M:%S') if pd.notna(first_punch_date) else None
                    
                    if len(emp_df) > 0 and pd.notna(emp_df.iloc[-1]['PunchDate']):
                        last_punch_date = emp_df.iloc[-1]['PunchDate']
                        out_time_str = last_punch_date.strftime('%H:%M:%S') if pd.notna(last_punch_date) else None
                    
                    total_punches_all_employees += total_punches_count
                    # Still include employee with zero/null values
                    employee_result = {
                        "empcode": str(empcode),
                        "name": employee_name,
                        "date": date_value.strftime('%Y-%m-%d') if date_value else None,
                        "in_time": in_time_str,
                        "out_time": out_time_str,
                        "total_time": "0:00",
                        "break_time": "0:00",
                        "work_time": "0:00",
                        "total_punches_count": total_punches_count,
                        "invalid_punches_count": len(invalid_emp_punches)
                    }
                    employee_results.append(employee_result)
                    
                    # Save/update to operational_data table even for invalid punches
                    if date_value:
                        operational_data.objects.update_or_create(
                            empcode=str(empcode),
                            date=date_value,
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
                
                # Find last punch - use the latest punch by time (regardless of mcid)
                # Last punch is not mandatory to be mcid=1, it can be any mcid
                # This handles cases where employee didn't punch out properly or has irregular patterns
                last_punch = emp_df.iloc[-1]  # Latest punch by time (already sorted by PunchDate)
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
                # 2. Last punch (any mcid) is always valid - not mandatory to be mcid=1
                # 3. Middle punches between first and last must follow alternating pattern: 1, 2, 1, 2...
                # 4. Only middle punches that break the 1,2 pattern are marked as invalid
                valid_punches, invalid_emp_punches = self._validate_mcid_pattern(between_punches, first_punch_time, last_punch_time, last_punch_mcid)
                
                # Add invalid punches to the invalid list (only middle punches that break pattern)
                invalid_punches.extend(invalid_emp_punches)
                
                # Calculate total time using first and last valid punches
                total_time = (last_punch_time - first_punch_time).total_seconds() / 3600  # Convert to hours
                
                # Calculate break time from valid punches only (excluding invalid middle punches)
                # Break time = sum of time differences between mcid "1" (out) and "2" (in) pairs in valid punches
                break_time = self._calculate_break_time(valid_punches)
                
                # Calculate work time
                work_time = total_time - break_time
                
                # Get employee name (try different possible column names)
                employee_name = ""
                if 'Name' in emp_df.columns and len(emp_df) > 0:
                    employee_name = str(emp_df.iloc[0].get('Name', ''))
                elif 'name' in emp_df.columns and len(emp_df) > 0:
                    employee_name = str(emp_df.iloc[0].get('name', ''))
                elif 'EmployeeName' in emp_df.columns and len(emp_df) > 0:
                    employee_name = str(emp_df.iloc[0].get('EmployeeName', ''))
                
                # Convert decimal hours to hours and minutes format
                total_time_formatted = self._convert_hours_to_hours_minutes(total_time)
                break_time_formatted = self._convert_hours_to_hours_minutes(break_time)
                work_time_formatted = self._convert_hours_to_hours_minutes(work_time)
                
                # Extract IN_TIME (first punch time) and OUT_TIME (last punch time)
                in_time_str = first_punch_time.strftime('%H:%M:%S') if pd.notna(first_punch_time) else None
                out_time_str = last_punch_time.strftime('%H:%M:%S') if pd.notna(last_punch_time) else None
                
                # Extract DATE (date from first punch)
                date_value = first_punch_time.date() if pd.notna(first_punch_time) else None
                
                total_punches_all_employees += total_punches_count
                
                # Format results - include IN_TIME, OUT_TIME, and DATE
                employee_result = {
                    "empcode": str(empcode),
                    "name": employee_name,
                    "date": date_value.strftime('%Y-%m-%d') if date_value else None,
                    "in_time": in_time_str,
                    "out_time": out_time_str,
                    "total_time": total_time_formatted,
                    "break_time": break_time_formatted,
                    "work_time": work_time_formatted,
                    "total_punches_count": total_punches_count,
                    "invalid_punches_count": len(invalid_emp_punches)  # Only middle punches that break pattern
                }
                
                employee_results.append(employee_result)
                
                # Save/update to operational_data table
                # If data for same empcode and date exists, update it; otherwise create new
                if date_value:
                    operational_data.objects.update_or_create(
                        empcode=str(empcode),
                        date=date_value,
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
        Between first and last punches, pattern should alternate: 1, 2, 1, 2...
        Returns: (valid_punches_df, invalid_punches_list)
        
        Rules:
        - First punch (mcid=2) is always valid
        - Last punch (any mcid) is always valid - NOT mandatory to be mcid=1
        - Middle punches between first and last must follow alternating pattern: 1, 2, 1, 2...
        - Only middle punches that break the 1,2 pattern are marked as invalid
        """
        if df.empty:
            return pd.DataFrame(), []
        
        # Reset index to ensure we have positional indices
        df = df.reset_index(drop=True)
        
        valid_indices = []
        invalid_punches = []
        
        # Find first punch index (mcid = "2")
        first_mask = df['PunchDate'] == first_punch_time
        first_indices = df[first_mask].index.tolist()
        if len(first_indices) > 0:
            first_idx = first_indices[0]
            # First punch is always valid (should be mcid=2)
            valid_indices.append(first_idx)
        
        # Find last punch index
        last_mask = df['PunchDate'] == last_punch_time
        last_indices = df[last_mask].index.tolist()
        if len(last_indices) > 0:
            last_idx = last_indices[-1]  # Get the last occurrence if multiple
            # Last punch is always valid (can be mcid=1 or mcid=2)
            # If mcid=2, it means employee didn't punch out properly
            valid_indices.append(last_idx)
        
        # Get punches strictly between first and last (exclude first and last)
        middle_mask = (df['PunchDate'] > first_punch_time) & (df['PunchDate'] < last_punch_time)
        middle_punches = df[middle_mask].copy()
        
        if not middle_punches.empty:
            # Pattern for middle punches should start with "1" then "2" (1, 2, 1, 2...)
            # After first punch (mcid=2), next should be mcid=1
            expected_next = '1'
            
            for idx in middle_punches.index:
                # Convert mcid to string for consistent comparison (handles both string and numeric)
                current_mcid = str(middle_punches.loc[idx, 'mcid']).strip()
                
                if current_mcid == expected_next:
                    # Pattern is correct - add to valid
                    valid_indices.append(idx)
                    # Toggle expected: 1 -> 2, 2 -> 1
                    expected_next = '2' if current_mcid == '1' else '1'
                else:
                    # Pattern is broken - mark as invalid
                    invalid_punches.append(middle_punches.loc[idx].to_dict())
                    # Don't update expected_next - continue with same expectation
                    # This allows the next punch to still be validated correctly
        
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
            # Convert mcid to string for consistent comparison (handles both string and numeric)
            current_mcid = str(df.iloc[i]['mcid']).strip()
            next_mcid = str(df.iloc[i + 1]['mcid']).strip()
            
            if current_mcid == '1' and next_mcid == '2':
                # This is a break period (out then in)
                time_diff = (df.iloc[i + 1]['PunchDate'] - df.iloc[i]['PunchDate']).total_seconds() / 3600
                break_time += time_diff
        
        return break_time
