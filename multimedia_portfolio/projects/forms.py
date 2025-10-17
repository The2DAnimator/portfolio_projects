from django import forms
from .models import Project, ProjectImage, ProjectFile, Category, PackageMockup

class ProjectForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = Project
        fields = ['title', 'description', 'project_type', 'categories', 
                 'cover_image', 'video_file', 'video_url', 'audio_file', 'is_published']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'project_type': forms.Select(attrs={'class': 'form-control'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'video_file': forms.FileInput(attrs={'class': 'form-control'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/watch?v=...'}),
            'audio_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'cover_image': 'Max 10MB. Allowed: jpg, jpeg, png, webp.',
            'video_file': 'Max 300MB. Allowed: mp4, mov, mkv, webm.',
            'video_url': 'Enter YouTube, Vimeo, or SoundCloud URL',
            'audio_file': 'Max 100MB. Allowed: mp3, wav, aac, flac, ogg.',
        }

class ProjectImageForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional caption'}),
        }
        help_texts = {
            'image': 'Max 10MB. Allowed: jpg, jpeg, png, webp.'
        }

class ProjectFileForm(forms.ModelForm):
    class Meta:
        model = ProjectFile
        fields = ['file', 'file_type', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'What is this file?'}),
        }
        help_texts = {
            'file': 'Max 100MB. Allowed: pdf, zip, rar, txt, doc, docx, ppt, pptx, xls, xlsx, psd, ai. SVG is not allowed.'
        }

class PackageMockupForm(forms.ModelForm):
    class Meta:
        model = PackageMockup
        fields = ['title', 'container_image', 'design_image', 'mask_image', 'design_pos_x', 'design_pos_y', 'design_scale', 'design_rotation', 'mask_opacity', 'mask_feather', 'mask_invert']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mockup title (optional)'}),
            'container_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'design_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'mask_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'design_pos_x': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': '0.1'}),
            'design_pos_y': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': '0.1'}),
            'design_scale': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200, 'step': '0.1'}),
            'design_rotation': forms.NumberInput(attrs={'class': 'form-control', 'min': -180, 'max': 180, 'step': '0.1'}),
            'mask_opacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': '1'}),
            'mask_feather': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200, 'step': '1'}),
            'mask_invert': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'container_image': 'Max 15MB. Allowed: jpg, jpeg, png, webp.',
            'design_image': 'Max 15MB. Allowed: jpg, jpeg, png, webp.',
            'mask_image': 'Max 10MB. Allowed: png, webp.'
        }
