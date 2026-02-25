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


class FetchPunchData(APIView):
    """
    API view to fetch punch data for all employees
    Requires: from_date and to_date as query parameters
    Usage: /api/fetch-punch-data/?from_date=12/03/2025&to_date=15/03/2025
    """
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
                
                csv_info = self._save_to_csv(entry_dataALL, from_date, to_date)
                
                if csv_info.get('status') != 'success':
                    return Response(
                        {
                            "error": "Failed to save CSV to blob storage",
                            "details": csv_info.get('message', 'Unknown error')
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                db_info = self._save_to_database(from_date, to_date, csv_info)
                
                if db_info.get('status') != 'success':
                    return Response(
                        {
                            "error": "Failed to save to database",
                            "details": db_info.get('message', 'Unknown error'),
                            "blob_url": csv_info.get('blob_url')  # Still return blob URL even if DB fails
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                return Response({
                    "id": db_info.get('id'),
                    "filename": csv_info.get('filename'),
                    "file_path": csv_info.get('blob_url')  # blob_url is the file path
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
    
    def _save_to_database(self, from_date, to_date, csv_info):
        """
        Save file metadata to database table (no data storage)
        """
        try:
            blob_url = csv_info.get('blob_url') or csv_info.get('file_path', '')
            
            if not blob_url:
                return {
                    "status": "error",
                    "message": "Blob URL is missing from CSV info"
                }
            
            try:
                punch_file = PunchDataFile.objects.create(
                    filename=csv_info.get('filename', ''),
                    file_path=csv_info.get('file_path', ''),  
                    blob_url=blob_url,
                    blob_name=csv_info.get('blob_name'),
                    container_name=csv_info.get('container_name'),
                    from_date=from_date,
                    to_date=to_date,
                    total_records=int(csv_info.get('total_records', 0)),
                    unique_employees=0  
                )
                
                return {
                    "status": "success",
                    "id": punch_file.id,
                    "message": "File metadata saved to database successfully",
                    "created_at": punch_file.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            except Exception as db_error:
                return {
                    "status": "error",
                    "message": f"Error saving to database: {str(db_error)}",
                    "error_type": type(db_error).__name__
                }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error in database save process: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def _save_to_csv(self, data, from_date, to_date):
        """
        Save the punch data to a CSV file and upload to blob storage
        """
        try:
            if isinstance(data, dict) and 'PunchData' in data:
                punch_data = data['PunchData']
            elif isinstance(data, list):
                punch_data = data
            else:
                punch_data = []
            
            if not punch_data:
                return {
                    "status": "no_data",
                    "message": "No punch data found to save"
                }
            
            df = pd.DataFrame(punch_data)
            
            date_str = from_date.replace('/', '_') + '_to_' + to_date.replace('/', '_')
            filename = f"punch_data_{date_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_buffer.seek(0)
            
            blob_info = self._upload_to_blob_storage(csv_buffer, filename)
            
            if blob_info['status'] == 'error':
                return blob_info
            
            return {
                "status": "success",
                "filename": filename,
                "blob_url": blob_info.get('blob_url'),
                "blob_name": blob_info.get('blob_name'),
                "container_name": blob_info.get('container_name'),
                "total_records": len(df),
                "columns": list(df.columns)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error saving to CSV: {str(e)}"
            }
    
    def _upload_to_blob_storage(self, file_buffer, filename):
        """
        Upload CSV file to Vercel Blob Storage using only BLOB_READ_WRITE_TOKEN
        """
        try:
            blob_read_write_token = env('BLOB_READ_WRITE_TOKEN', default=None)
            
            if not blob_read_write_token:
                return {
                    "status": "error",
                    "message": "BLOB_READ_WRITE_TOKEN not found in environment variables. Please set BLOB_READ_WRITE_TOKEN in your .env file."
                }
            
            vercel_blob_api_url = "https://blob.vercel-storage.com"
            
            file_buffer.seek(0)
            
            file_data = file_buffer.read()
            
            try:
                file_buffer.seek(0)
                files = {
                    'file': (filename, file_buffer, 'text/csv')
                }
                data = {
                    'filename': filename
                }
                headers = {
                    "Authorization": f"Bearer {blob_read_write_token}"
                }
                
                response = requests.post(
                    f"{vercel_blob_api_url}/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code not in [200, 201]:
                    file_buffer.seek(0)
                    headers_put = {
                        "Authorization": f"Bearer {blob_read_write_token}",
                        "Content-Type": "text/csv",
                        "x-content-type": "text/csv"
                    }
                    response = requests.put(
                        f"{vercel_blob_api_url}/{filename}",
                        data=file_data,
                        headers=headers_put,
                        timeout=30
                    )
                
                if response.status_code not in [200, 201]:
                    return {
                        "status": "error",
                        "message": f"Vercel Blob Storage returned error: {response.text}",
                        "status_code": response.status_code
                    }
                
                try:
                    response_data = response.json()
                    blob_url = (
                        response_data.get('url') or 
                        response_data.get('blobUrl') or 
                        response_data.get('downloadUrl') or 
                        response_data.get('path') or
                        f"{vercel_blob_api_url}/{filename}"
                    )
                except:
                    blob_url = f"{vercel_blob_api_url}/{filename}"
                
                return {
                    "status": "success",
                    "blob_url": blob_url,
                    "blob_name": filename,
                    "container_name": "vercel-blob"  
                }
                
            except requests.exceptions.RequestException as upload_error:
                return {
                    "status": "error",
                    "message": f"Error uploading file to Vercel Blob Storage: {str(upload_error)}",
                    "error_type": type(upload_error).__name__
                }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error in blob storage upload: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def _perform_operations(self, data):
        """
        Perform various operations on the punch data
        """
        try:
            if isinstance(data, dict) and 'PunchData' in data:
                punch_data = data['PunchData']
            elif isinstance(data, list):
                punch_data = data
            else:
                punch_data = []
            
            if not punch_data:
                return {
                    "status": "no_data",
                    "message": "No punch data found for operations"
                }
            
            df = pd.DataFrame(punch_data)
            
            if 'PunchDate' in df.columns:
                df['PunchDate'] = pd.to_datetime(df['PunchDate'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
            
            operations = {}
            operations['total_records'] = len(df)
            
            if 'Empcode' in df.columns:
                operations['unique_employees'] = int(df['Empcode'].nunique())
                operations['employee_list'] = df['Empcode'].unique().tolist()
            
            if 'Empcode' in df.columns:
                records_per_emp = df['Empcode'].value_counts().to_dict()
                operations['records_per_employee'] = convert_to_native_types(records_per_emp)
            
            if 'mcid' in df.columns:
                mcid_dist = df['mcid'].value_counts().to_dict()
                operations['mcid_distribution'] = convert_to_native_types(mcid_dist)
            
            if 'PunchDate' in df.columns and not df['PunchDate'].isna().all():
                punch_by_hour = df.groupby(df['PunchDate'].dt.hour).size().to_dict() if 'PunchDate' in df.columns else {}
                operations['time_analysis'] = {
                    'earliest_punch': df['PunchDate'].min().strftime('%Y-%m-%d %H:%M:%S') if pd.notna(df['PunchDate'].min()) else None,
                    'latest_punch': df['PunchDate'].max().strftime('%Y-%m-%d %H:%M:%S') if pd.notna(df['PunchDate'].max()) else None,
                    'punch_count_by_hour': convert_to_native_types(punch_by_hour)
                }
            
            if 'Empcode' in df.columns:
                employee_punch_counts = df['Empcode'].value_counts()
                operations['employees_with_multiple_punches'] = {
                    'count': int((employee_punch_counts > 1).sum()),
                    'employee_codes': employee_punch_counts[employee_punch_counts > 1].index.tolist()
                }
            
            if 'Empcode' in df.columns:
                top_employees = df['Empcode'].value_counts().head(10)
                operations['top_10_active_employees'] = {
                    'empcode': top_employees.index.tolist(),
                    'punch_count': convert_to_native_types(top_employees.values.tolist())
                }
            
            operations = convert_to_native_types(operations)
            
            return {
                "status": "success",
                "operations": operations
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error performing operations: {str(e)}"
            }


class FetchPunchDataWithParams(APIView):
    """
    API view to fetch punch data with three variables: Empcode, FromDate, ToDate
    Requires: empcode, from_date, and to_date as query parameters
    Usage: /api/fetch-punch-data-params/?empcode=0010&from_date=12/03/2025&to_date=12/03/2025
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
        
        api_url = (
            f"https://api.etimeoffice.com/api/DownloadPunchDataMCID"
            f"?Empcode={empcode}&FromDate={from_date}_00:00&ToDate={to_date}_22:00"
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
            
            empcodes = [code.strip() for code in empcode.split(',') if code.strip()]
            
            if not empcodes:
                return Response(
                    {"error": "Invalid empcode parameter"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
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


