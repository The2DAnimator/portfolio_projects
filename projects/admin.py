from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Category, Project, ProjectImage, ProjectFile

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1

class ProjectFileInline(admin.TabularInline):
    model = ProjectFile
    extra = 1

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'project_type', 'is_published', 'created_at']
    list_filter = ['project_type', 'is_published', 'created_at', 'categories']
    search_fields = ['title', 'description', 'owner__username']
    inlines = [ProjectImageInline, ProjectFileInline]