from django.db import models

# Create your models here.
class VerificationCode(models.Model):
    phone_number = models.CharField(max_length=11)
    verification_code = models.CharField(max_length=6)
    created_time = models.DateTimeField()

