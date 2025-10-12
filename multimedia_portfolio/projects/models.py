from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from embed_video.fields import EmbedVideoField

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Project(models.Model):
    PROJECT_TYPES = [
        ('image', 'Image Gallery'),
        ('video', 'Video Project'),
        ('audio', 'Audio Project'),
        ('mixed', 'Mixed Media'),
        ('animation', 'Animation'),
        ('graphic', 'Graphic Design'),
        ('photography', 'Photography'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES)
    categories = models.ManyToManyField(Category, blank=True)
    
    # Media fields
    cover_image = models.ImageField(upload_to='project_covers/', blank=True, null=True)
    video_url = EmbedVideoField(blank=True, null=True)
    audio_file = models.FileField(upload_to='project_audio/', blank=True, null=True)
    
    # Owner and timestamps
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})
    
    def is_owner(self, user):
        return self.owner == user or user.is_staff

class ProjectImage(models.Model):
    project = models.ForeignKey(Project, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='project_images/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for {self.project.title}"

class ProjectFile(models.Model):
    FILE_TYPES = [
        ('document', 'Document'),
        ('source', 'Source File'),
        ('asset', 'Asset'),
        ('other', 'Other'),
    ]
    
    project = models.ForeignKey(Project, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(upload_to='project_files/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    description = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"File for {self.project.title}"