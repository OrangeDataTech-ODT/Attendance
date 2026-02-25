from django.db import models

class mcid(models.Model):
    name = models.CharField(max_length=100)
    empcode = models.CharField(max_length=10)
    punch_date = models.CharField(max_length=20)
    punch_time = models.CharField(max_length=20)
    m_flag = models.CharField(max_length=2, null=True, blank=True)
    mcid = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'punch_data_mcid'
        unique_together = [['empcode', 'punch_date', 'punch_time', 'mcid']]
        verbose_name = 'MCID Data'
        verbose_name_plural = 'MCID Data'
    
    def __str__(self):
        return f"{self.name} - {self.empcode} - {self.punch_date} {self.punch_time}" 