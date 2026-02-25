from django.db import models
from django.utils import timezone


class EmailLog(models.Model):
    """
    Model to track sent emails to prevent duplicate notifications
    """
    empcode = models.CharField(max_length=10, db_index=True)
    email_type = models.CharField(max_length=50)  # 'invalid_punch', 'punch_reminder'
    sent_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)  # Date for which the email was sent
    details = models.JSONField(null=True, blank=True)  # Store additional details
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_log'
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'
        # Prevent duplicate emails for same employee, type, and date
        unique_together = [['empcode', 'email_type', 'date']]
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.empcode} - {self.email_type} - {self.date}"

