from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Follow(models.Model):
    user = models.ForeignKey(User, related_name='following', on_delete=models.CASCADE)
    target = models.ForeignKey(User, related_name='followers', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'target')

    def __str__(self):
        return f"{self.user.username} follows {self.target.username}"


class UserSecuritySettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_settings')
    email_2fa_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SecuritySettings({self.user.username})"


class Email2FAToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_2fa_tokens')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Email2FAToken(user={self.user.username}, used={self.is_used})"


class UserStorageSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='storage_settings')
    quota_mb = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"StorageSettings({self.user.username}: {self.quota_mb or 'default'} MB)"
