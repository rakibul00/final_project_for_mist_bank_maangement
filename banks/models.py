from django.db import models

class Bank(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True, null=True, help_text="Optional bank code (e.g., IBBL, SONALI)")
    is_active = models.BooleanField(default=True, help_text="Only active banks can be selected by users")

    class Meta:
        ordering = ['name']
        verbose_name = 'Bank'
        verbose_name_plural = 'Banks'

    def __str__(self):
        if self.code:
            return f"{self.name} ({self.code})"
        return self.name
