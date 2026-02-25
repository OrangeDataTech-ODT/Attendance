from django.core.management.base import BaseCommand
from django.utils import timezone
import pytz
import requests
import base64
import environ
import os
import logging
from django.conf import settings
from datetime import datetime
from ...models.all_data import all_data
from ...views.all_data_views import _save_to_all_data_model

logger = logging.getLogger(__name__)

# Initialize environment
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


class Command(BaseCommand):
    help = 'Fetches and saves InOut punch data for the current day (IST timezone)'

    def handle(self, *args, **options):
        # Get current date in IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        current_time_ist = timezone.now().astimezone(ist)
        current_date = current_time_ist.date()
        
        # Format date as DD/MM/YYYY for the API
        from_date = current_date.strftime('%d/%m/%Y')
        to_date = from_date  # Same day
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Fetching punch data for {from_date} (IST: {current_time_ist.strftime("%Y-%m-%d %H:%M:%S")})'
            )
        )

#For manual testing and current

# class Command(BaseCommand):
#     help = 'Fetches and saves InOut punch data for the current day (IST timezone)'

#     def handle(self, *args, **options):
#         # TEMP override for testing – set this to a string date or None
#         TEST_DATE = '20/01/2026'  # e.g. '20/01/2026' for testing

#         if TEST_DATE:
#             # Use manual test date
#             from_date = TEST_DATE
#             to_date = TEST_DATE
#             current_time_ist = timezone.now()  # just for logging
#         else:
#             # Get current date in IST timezone (normal behavior)
#             ist = pytz.timezone('Asia/Kolkata')
#             current_time_ist = timezone.now().astimezone(ist)
#             current_date = current_time_ist.date()

#             # Format date as DD/MM/YYYY for the API
#             from_date = current_date.strftime('%d/%m/%Y')
#             to_date = from_date  # Same day

#         self.stdout.write(
#             self.style.SUCCESS(
#                 f'Fetching punch data for {from_date} (IST: {current_time_ist.strftime("%Y-%m-%d %H:%M:%S")})'
#             )
#         )
        # ... rest of your existing code unchanged ...
        
        # Build API URL
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
                self.stdout.write(
                    self.style.SUCCESS(f'API response received successfully')
                )
                
                # Save data to all_data model
                # The _save_to_all_data_model function checks for existing records
                # and only updates if data has changed, preventing duplicate entries
                created_count, updated_count, skipped_count, save_errors = _save_to_all_data_model(entry_data)
                total_processed = created_count + updated_count + skipped_count
                
                if save_errors:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Processed {total_processed} records: {created_count} created, {updated_count} updated, {skipped_count} skipped, {len(save_errors)} errors'
                        )
                    )
                    for error in save_errors[:5]:  # Show first 5 errors
                        self.stdout.write(
                            self.style.ERROR(f'Error: {error}')
                        )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully processed {total_processed} records: {created_count} created, {updated_count} updated, {skipped_count} skipped'
                        )
                    )
                
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'API returned status {response.status_code}: {response.text}'
                    )
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'An error occurred: {str(e)}')
            )
            logger.error(f'Error in fetch_daily_punch_data command: {str(e)}', exc_info=True)

