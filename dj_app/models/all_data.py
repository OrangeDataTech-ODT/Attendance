from django.db import models

class all_data(models.Model):
    empcode= models.CharField(max_length=10)
    in_time= models.CharField(max_length=10)
    out_time= models.CharField(max_length=10)
    work_time= models.CharField(max_length=10)
    over_time= models.CharField(max_length=10)
    break_time= models.CharField(max_length=10)
    status= models.CharField(max_length=10)
    date_string= models.DateField()
    remark= models.CharField(max_length=100)
    erl_out= models.CharField(max_length=10)
    late_in= models.CharField(max_length=10)
    name= models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        db_table = 'punch_data_all'
        unique_together = ['empcode', 'date_string'] 








