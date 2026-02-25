from django.db import models
from django.utils import timezone
import json

# Create your models here.

class PunchDataFile(models.Model):
    """
    Model to store punch data CSV files and their metadata
    """
    # File metadata
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, null=True, blank=True, help_text="Blob storage URL or local file path")
    blob_url = models.URLField(max_length=1000, null=True, blank=True, help_text="Azure Blob Storage URL")
    blob_name = models.CharField(max_length=255, null=True, blank=True, help_text="Blob name in storage")
    container_name = models.CharField(max_length=255, null=True, blank=True, help_text="Container name in blob storage")
    from_date = models.CharField(max_length=50)
    to_date = models.CharField(max_length=50)
    
    # Statistics
    total_records = models.IntegerField(default=0)
    unique_employees = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'punch_data_files'
        ordering = ['-created_at']
        verbose_name = 'Punch Data File'
        verbose_name_plural = 'Punch Data Files'
    
    def __str__(self):
        return f"{self.filename} ({self.total_records} records) - {self.from_date} to {self.to_date}"
