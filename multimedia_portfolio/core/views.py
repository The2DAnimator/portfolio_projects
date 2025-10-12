from django.shortcuts import render
from django.contrib.auth.models import User
from projects.models import Project

def home(request):
    # Get featured projects (published projects with cover images)
    featured_projects = Project.objects.filter(
        is_published=True
    ).exclude(cover_image='').order_by('-created_at')[:9]
    
    # Get statistics
    total_projects = Project.objects.filter(is_published=True).count()
    total_users = User.objects.count()
    
    context = {
        'featured_projects': featured_projects,
        'total_projects': total_projects,
        'total_users': total_users,
    }
    
    return render(request, 'core/home.html', context)