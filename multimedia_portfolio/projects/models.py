from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from embed_video.fields import EmbedVideoField
import os
from django.utils.deconstruct import deconstructible

@deconstructible
class MaxSizeValidator:
    def __init__(self, max_mb):
        self.max_mb = int(max_mb)

    def __call__(self, file_obj):
        if not file_obj or not hasattr(file_obj, 'size'):
            return
        limit = self.max_mb * 1024 * 1024
        if file_obj.size > limit:
            raise models.ValidationError(f"File too large. Max size is {self.max_mb}MB.")

    def __repr__(self):
        return f"MaxSizeValidator(max_mb={self.max_mb})"


@deconstructible
class ExtensionValidator:
    def __init__(self, allowed_exts):
        # store as sorted tuple for determinism/serialization
        self.allowed_exts = tuple(sorted(allowed_exts)) if allowed_exts else tuple()

    def __call__(self, file_obj):
        if not file_obj:
            return
        name = getattr(file_obj, 'name', '')
        ext = os.path.splitext(name)[1].lower()
        if ext and ext.startswith('.'):
            ext = ext[1:]
        if self.allowed_exts and ext not in self.allowed_exts:
            raise models.ValidationError("Unsupported file type.")

    def __repr__(self):
        return f"ExtensionValidator(allowed_exts={self.allowed_exts})"

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
    cover_image = models.ImageField(
        upload_to='project_covers/', blank=True, null=True,
        validators=[MaxSizeValidator(10), ExtensionValidator({'jpg','jpeg','png','webp'})]
    )
    video_file = models.FileField(
        upload_to='project_video/', blank=True, null=True,
        validators=[MaxSizeValidator(300), ExtensionValidator({'mp4','mov','mkv','webm'})]
    )
    video_url = EmbedVideoField(blank=True, null=True)
    audio_file = models.FileField(
        upload_to='project_audio/', blank=True, null=True,
        validators=[MaxSizeValidator(100), ExtensionValidator({'mp3','wav','aac','flac','ogg'})]
    )
    
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
    image = models.ImageField(
        upload_to='project_images/',
        validators=[MaxSizeValidator(10), ExtensionValidator({'jpg','jpeg','png','webp'})]
    )
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
    file = models.FileField(
        upload_to='project_files/',
        validators=[MaxSizeValidator(100), ExtensionValidator({'pdf','zip','rar','txt','doc','docx','ppt','pptx','xls','xlsx','psd','ai'})]
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    description = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"File for {self.project.title}"

class ProjectLike(models.Model):
    project = models.ForeignKey('Project', related_name='likes', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='project_likes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.username} likes {self.project.title}"

class PackageMockup(models.Model):
    TEMPLATE_CHOICES = [
        ('freeform', 'Freeform Container'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='package_mockups')
    title = models.CharField(max_length=200)
    template = models.CharField(max_length=32, choices=TEMPLATE_CHOICES, default='freeform')
    container_image = models.ImageField(
        upload_to='mockups/containers/',
        validators=[MaxSizeValidator(15), ExtensionValidator({'jpg','jpeg','png','webp'})]
    )
    design_image = models.ImageField(
        upload_to='mockups/designs/',
        validators=[MaxSizeValidator(15), ExtensionValidator({'jpg','jpeg','png','webp'})]
    )
    generated_image = models.ImageField(
        upload_to='mockups/generated/', blank=True, null=True,
        validators=[MaxSizeValidator(20), ExtensionValidator({'jpg','jpeg','png','webp'})]
    )
    design_pos_x = models.FloatField(default=50.0, blank=True)
    design_pos_y = models.FloatField(default=50.0, blank=True)
    design_scale = models.FloatField(default=60.0, blank=True)
    design_rotation = models.FloatField(default=0.0, blank=True)
    mask_image = models.ImageField(
        upload_to='mockups/masks/', blank=True, null=True,
        validators=[MaxSizeValidator(10), ExtensionValidator({'png','webp'})]
    )
    mask_opacity = models.FloatField(default=100.0, blank=True)
    mask_feather = models.FloatField(default=0.0, blank=True)
    mask_invert = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Mockup: {self.title} by {self.owner.username}"