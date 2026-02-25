from django.db import models

class operational_data(models.Model):
    empcode= models.CharField(max_length=10)
    name= models.CharField(max_length=100)
    date= models.DateField(null=True,blank=True)
    in_time= models.CharField(max_length=20,null=True,blank=True)
    out_time= models.CharField(max_length=20,null=True,blank=True)
    total_time= models.CharField(max_length=10,null=True,blank=True)
    break_time= models.CharField(max_length=10,null=True,blank=True)
    work_time= models.CharField(max_length=10,null=True,blank=True)
    total_punches_count= models.IntegerField(null=True,blank=True)
    invalid_punches_count= models.IntegerField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'punch_data_operational'
        unique_together = ['empcode', 'date']  # Prevent duplicate entries for same empcode and date



