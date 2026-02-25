from django.db import models


class Employee(models.Model):
    """
    Employee details model to store employee information including email
    """
    empcode = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_details'
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['empcode']

    def __str__(self):
        return f"{self.name} ({self.empcode})"












