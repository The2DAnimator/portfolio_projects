from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Project, ProjectImage, ProjectFile
from .forms import ProjectForm, ProjectImageForm, ProjectFileForm

@login_required
def dashboard(request):
    projects = Project.objects.filter(owner=request.user)
    return render(request, 'projects/dashboard.html', {'projects': projects})

@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            form.save_m2m()  # Save many-to-many data for categories
            messages.success(request, 'Project created successfully!')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    
    return render(request, 'projects/project_form.html', {
        'form': form,
        'form_type': 'create'
    })

@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if not project.is_owner(request.user):
        return HttpResponseForbidden("You don't have permission to view this project.")
    
    image_form = ProjectImageForm()
    file_form = ProjectFileForm()
    
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'image_form': image_form,
        'file_form': file_form,
    })

@login_required
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if not project.is_owner(request.user):
        return HttpResponseForbidden("You don't have permission to edit this project.")
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated successfully!')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    
    return render(request, 'projects/project_form.html', {
        'form': form,
        'project': project,
        'form_type': 'update'
    })

@login_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if not project.is_owner(request.user):
        return HttpResponseForbidden("You don't have permission to delete this project.")
    
    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Project deleted successfully!')
        return redirect('projects:dashboard')
    
    return render(request, 'projects/project_confirm_delete.html', {'project': project})

@login_required
def add_project_image(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    
    if not project.is_owner(request.user):
        return HttpResponseForbidden("You don't have permission to add images to this project.")
    
    if request.method == 'POST':
        form = ProjectImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.project = project
            image.save()
            messages.success(request, 'Image added successfully!')
    
    return redirect('projects:project_detail', pk=project.pk)

@login_required
def add_project_file(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    
    if not project.is_owner(request.user):
        return HttpResponseForbidden("You don't have permission to add files to this project.")
    
    if request.method == 'POST':
        form = ProjectFileForm(request.POST, request.FILES)
        if form.is_valid():
            project_file = form.save(commit=False)
            project_file.project = project
            project_file.save()
            messages.success(request, 'File added successfully!')
    
    return redirect('projects:project_detail', pk=project.pk)