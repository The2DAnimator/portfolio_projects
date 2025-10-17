def _get_user_storage_usage_bytes(user):
    total = 0
    try:
        from django.core.files.storage import default_storage
        # Projects
        for p in Project.objects.filter(owner=user):
            for f in [p.cover_image, p.video_file, p.audio_file]:
                try:
                    if f and getattr(f, 'name', None):
                        size = getattr(f, 'size', None)
                        if size is None and default_storage.exists(f.name):
                            size = default_storage.size(f.name)
                        if size:
                            total += int(size)
                except Exception:
                    continue
        # Project images
        for pi in ProjectImage.objects.filter(project__owner=user):
            try:
                f = pi.image
                if f and getattr(f, 'name', None):
                    size = getattr(f, 'size', None)
                    if size is None and default_storage.exists(f.name):
                        size = default_storage.size(f.name)
                    if size:
                        total += int(size)
            except Exception:
                continue
        # Project files
        for pf in ProjectFile.objects.filter(project__owner=user):
            try:
                f = pf.file
                if f and getattr(f, 'name', None):
                    size = getattr(f, 'size', None)
                    if size is None and default_storage.exists(f.name):
                        size = default_storage.size(f.name)
                    if size:
                        total += int(size)
            except Exception:
                continue
        # Mockups
        for m in PackageMockup.objects.filter(owner=user):
            for f in [m.container_image, m.design_image, m.generated_image, m.mask_image]:
                try:
                    if f and getattr(f, 'name', None):
                        size = getattr(f, 'size', None)
                        if size is None and default_storage.exists(f.name):
                            size = default_storage.size(f.name)
                        if size:
                            total += int(size)
                except Exception:
                    continue
    except Exception:
        return total
    return total

def _would_exceed_quota(user, additional_bytes):
    try:
        # Prefer per-user quota if configured
        user_quota = None
        try:
            uss = UserStorageSettings.objects.filter(user=user).only('quota_mb').first()
            if uss and uss.quota_mb:
                user_quota = int(uss.quota_mb)
        except Exception:
            user_quota = None
        quota_mb = int(user_quota if user_quota is not None else (getattr(settings, 'USER_STORAGE_QUOTA_MB', 0) or 0))
    except Exception:
        quota_mb = 0
    if quota_mb <= 0:
        return False
    used = _get_user_storage_usage_bytes(user)
    return (used + max(0, int(additional_bytes))) > (quota_mb * 1024 * 1024)

def _incoming_files_size(request_files, keys):
    total = 0
    for k in keys:
        f = request_files.get(k)
        if f and hasattr(f, 'size'):
            try:
                total += int(f.size)
            except Exception:
                pass
    return total

def _process_image_strip_metadata(uploaded_file):
    if Image is None or not uploaded_file:
        return None
    try:
        with Image.open(uploaded_file) as im:
            im.load()
            has_alpha = ('A' in im.getbands()) or (im.mode in ('RGBA', 'LA'))
            rgb = im.convert('RGBA') if has_alpha else im.convert('RGB')
            out = BytesIO()
            if has_alpha:
                # Preserve alpha in PNG and strip metadata
                rgb.save(out, format='PNG', optimize=True)
                new_ext = 'png'
            else:
                rgb.save(out, format='JPEG', quality=90, optimize=True)
                new_ext = 'jpg'
            content = ContentFile(out.getvalue())
            base = os.path.splitext(getattr(uploaded_file, 'name', 'upload'))[0]
            new_name = f"{os.path.basename(base)}_clean.{new_ext}"
            return content, new_name
    except Exception:
        return None
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from .models import Project, ProjectImage, ProjectFile, ProjectLike, PackageMockup, Category
from accounts.models import Follow, UserStorageSettings
from .forms import ProjectForm, ProjectImageForm, ProjectFileForm, PackageMockupForm
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
import os
import time
from io import BytesIO
try:
    from PIL import Image, ImageOps, ImageFilter, ImageChops
except Exception:
    Image = None

def compose_mockup_image(mockup):
    if Image is None or not mockup.container_image or not mockup.design_image:
        return
    try:
        with Image.open(mockup.container_image) as _base_im:
            base = _base_im.convert('RGBA').copy()
        with Image.open(mockup.design_image) as _design_im:
            design = _design_im.convert('RGBA').copy()
        target_w = max(1, int(base.width * (mockup.design_scale / 100.0)))
        ratio = target_w / float(design.width)
        target_h = max(1, int(design.height * ratio))
        design = design.resize((target_w, target_h), Image.LANCZOS)
        if mockup.mask_image:
            with Image.open(mockup.mask_image) as _mask_im:
                mask = _mask_im.convert('L').resize((design.width, design.height), Image.LANCZOS).copy()
            if getattr(mockup, 'mask_invert', False):
                mask = ImageOps.invert(mask)
            feather = max(0.0, float(getattr(mockup, 'mask_feather', 0.0)))
            if feather > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
            opacity = max(0.0, min(100.0, float(getattr(mockup, 'mask_opacity', 100.0)))) / 100.0
            if design.mode != 'RGBA':
                design = design.convert('RGBA')
            existing_alpha = design.split()[-1]
            mask_scaled = mask.point(lambda p: int(p * opacity))
            combined_alpha = ImageChops.multiply(existing_alpha, mask_scaled)
            design.putalpha(combined_alpha)
        if mockup.design_rotation:
            design = design.rotate(-mockup.design_rotation, resample=Image.BICUBIC, expand=True)
        pos_x = int((mockup.design_pos_x / 100.0) * base.width - design.width / 2)
        pos_y = int((mockup.design_pos_y / 100.0) * base.height - design.height / 2)
        composed = Image.new('RGBA', base.size)
        composed.paste(base, (0, 0))
        composed.alpha_composite(design, (pos_x, pos_y))
        out_io = BytesIO()
        composed.convert('RGB').save(out_io, format='JPEG', quality=90)
        out_content = ContentFile(out_io.getvalue())
        filename = f"mockup_{mockup.id}_{int(timezone.now().timestamp())}.jpg"
        mockup.generated_image.save(filename, out_content, save=True)
    except Exception:
        pass

def _safe_delete_file(path, attempts=5, delay=0.2):
    if not path:
        return
    for i in range(attempts):
        try:
            if os.path.exists(path):
                os.remove(path)
            return
        except PermissionError:
            time.sleep(delay)
        except Exception:
            return

@login_required
def dashboard(request):
    projects = Project.objects.filter(owner=request.user)
    used_bytes = _get_user_storage_usage_bytes(request.user)
    try:
        uss = UserStorageSettings.objects.filter(user=request.user).only('quota_mb').first()
        if uss and uss.quota_mb:
            quota_mb = int(uss.quota_mb)
        else:
            quota_mb = int(getattr(settings, 'USER_STORAGE_QUOTA_MB', 0) or 0)
    except Exception:
        quota_mb = 0
    quota_bytes = quota_mb * 1024 * 1024
    percent = 0
    if quota_bytes > 0:
        percent = min(100, int((used_bytes / quota_bytes) * 100)) if used_bytes else 0
    ctx = {
        'projects': projects,
        'quota_mb': quota_mb,
        'used_mb': round(used_bytes / (1024 * 1024), 2),
        'quota_percent': percent,
    }
    return render(request, 'projects/dashboard.html', ctx)

def project_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    # Always render public view. If not published, only owner may view; others forbidden.
    if not project.is_published:
        if not (request.user.is_authenticated and project.is_owner(request.user)):
            return HttpResponseForbidden("This project is not published.")
    likes_count = ProjectLike.objects.filter(project=project).count()
    liked = False
    if request.user.is_authenticated:
        liked = ProjectLike.objects.filter(project=project, user=request.user).exists()
    followers_count = 0
    following_count = 0
    is_following = False
    try:
        from accounts.models import Follow
        followers_count = Follow.objects.filter(target=project.owner).count()
        following_count = Follow.objects.filter(user=project.owner).count()
        if request.user.is_authenticated:
            is_following = Follow.objects.filter(user=request.user, target=project.owner).exists()
    except Exception:
        pass
    context = {
        'project': project,
        'likes_count': likes_count,
        'liked': liked,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
        'is_owner': False,
        'messages': [],
    }
    return render(request, 'projects/project_public_detail.html', context)

def public_projects(request):
    projects = Project.objects.filter(is_published=True)
    q = request.GET.get('q', '').strip()
    project_type = request.GET.get('type', '').strip()
    category_id = request.GET.get('category', '').strip()
    sort = (request.GET.get('sort') or 'created').strip()  # created | likes | title
    direction = (request.GET.get('dir') or 'desc').strip()  # desc | asc
    # Proper combined filter for title/description
    if q:
        projects = projects.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if project_type:
        try:
            projects = projects.filter(project_type=project_type)
        except Exception:
            pass
    if category_id:
        try:
            projects = projects.filter(categories__id=int(category_id))
        except Exception:
            pass

    # annotate likes count for sorting/display
    projects = projects.annotate(likes_count=Count('likes'))

    # sorting
    if sort == 'likes':
        order_field = '-likes_count' if direction == 'desc' else 'likes_count'
    elif sort == 'title':
        order_field = 'title' if direction == 'asc' else '-title'
    else:  # created
        order_field = '-created_at' if direction == 'desc' else 'created_at'
    projects = projects.order_by(order_field)

    # Build type choices from model if available
    type_choices = []
    try:
        field = Project._meta.get_field('project_type')
        if getattr(field, 'choices', None):
            type_choices = list(field.choices)
    except Exception:
        type_choices = []

    # Category choices
    categories = Category.objects.all().order_by('name')

    # Pagination
    try:
        page_size = int(request.GET.get('page_size') or 12)
    except Exception:
        page_size = 12
    paginator = Paginator(projects, page_size)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    return render(request, 'projects/public_list.html', {
        'projects': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'page_size': page_size,
        'q': q,
        'active_type': project_type,
        'type_choices': type_choices,
        'categories': categories,
        'active_category': category_id,
        'sort': sort,
        'dir': direction,
    })

@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            # Quota check for incoming files
            add_bytes = _incoming_files_size(request.FILES, ['cover_image', 'video_file', 'audio_file'])
            if _would_exceed_quota(request.user, add_bytes):
                messages.error(request, 'Upload would exceed your storage quota. Please remove some files or upload smaller files.')
                return render(request, 'projects/project_form.html', {'form': form, 'form_type': 'create'})

            project = form.save(commit=False)
            project.owner = request.user
            # Strip metadata on images if provided
            if request.FILES.get('cover_image'):
                processed = _process_image_strip_metadata(request.FILES['cover_image'])
                if processed:
                    content, new_name = processed
                    project.cover_image.save(new_name, content, save=False)
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
    
    # Allow viewing if the project is published or the current user is the owner/staff
    if not (project.is_published or project.is_owner(request.user)):
        return HttpResponseForbidden("You don't have permission to view this project.")
    
    image_form = ProjectImageForm()
    file_form = ProjectFileForm()
    
    likes_count = ProjectLike.objects.filter(project=project).count()
    liked = ProjectLike.objects.filter(project=project, user=request.user).exists()
    followers_count = Follow.objects.filter(target=project.owner).count()
    following_count = Follow.objects.filter(user=project.owner).count()
    is_following = Follow.objects.filter(user=request.user, target=project.owner).exists()
    
    context = {
        'project': project,
        'image_form': image_form,
        'file_form': file_form,
        'likes_count': likes_count,
        'liked': liked,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
        'is_owner': project.is_owner(request.user),
        'messages': [],
    }
    
    return render(request, 'projects/project_detail.html', context)

@login_required
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if not project.is_owner(request.user):
        return HttpResponseForbidden("You don't have permission to edit this project.")
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            add_bytes = _incoming_files_size(request.FILES, ['cover_image', 'video_file', 'audio_file'])
            if _would_exceed_quota(request.user, add_bytes):
                messages.error(request, 'Upload would exceed your storage quota. Please remove some files or upload smaller files.')
                return render(request, 'projects/project_form.html', {'form': form, 'project': project, 'form_type': 'update'})
            proj = form.save(commit=False)
            if request.FILES.get('cover_image'):
                processed = _process_image_strip_metadata(request.FILES['cover_image'])
                if processed:
                    content, new_name = processed
                    proj.cover_image.save(new_name, content, save=False)
            proj.save()
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
            add_bytes = _incoming_files_size(request.FILES, ['image'])
            if _would_exceed_quota(request.user, add_bytes):
                messages.error(request, 'Upload would exceed your storage quota. Please remove some files or upload smaller files.')
            else:
                image = form.save(commit=False)
                image.project = project
                if request.FILES.get('image'):
                    processed = _process_image_strip_metadata(request.FILES['image'])
                    if processed:
                        content, new_name = processed
                        image.image.save(new_name, content, save=False)
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
            add_bytes = _incoming_files_size(request.FILES, ['file'])
            if _would_exceed_quota(request.user, add_bytes):
                messages.error(request, 'Upload would exceed your storage quota. Please remove some files or upload smaller files.')
            else:
                project_file = form.save(commit=False)
                project_file.project = project
                project_file.save()
                messages.success(request, 'File added successfully!')
    
    return redirect('projects:project_detail', pk=project.pk)

@login_required
def toggle_like(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    project = get_object_or_404(Project, pk=project_id, is_published=True)
    like, created = ProjectLike.objects.get_or_create(project=project, user=request.user)
    if created:
        liked = True
    else:
        like.delete()
        liked = False
    count = ProjectLike.objects.filter(project=project).count()
    return JsonResponse({'liked': liked, 'count': count})

# Mockups
@login_required
def mockup_list(request):
    mockups = PackageMockup.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'projects/mockups/list.html', {'mockups': mockups})

@login_required
def mockup_create(request):
    if request.method == 'POST':
        form = PackageMockupForm(request.POST, request.FILES)
        if form.is_valid():
            add_bytes = _incoming_files_size(request.FILES, ['container_image', 'design_image', 'mask_image'])
            if _would_exceed_quota(request.user, add_bytes):
                messages.error(request, 'Upload would exceed your storage quota. Please remove some files or upload smaller files.')
            else:
                mockup = form.save(commit=False)
                mockup.owner = request.user
                mockup.title = mockup.title or f"Mockup {timezone.now():%Y-%m-%d %H:%M}"
                # Process images
                for field in ['container_image', 'design_image', 'mask_image']:
                    if request.FILES.get(field):
                        processed = _process_image_strip_metadata(request.FILES[field])
                        if processed:
                            content, new_name = processed
                            getattr(mockup, field).save(new_name, content, save=False)
                mockup.save()
                compose_mockup_image(mockup)
                messages.success(request, 'Mockup created successfully!')
                return redirect('projects:mockup_detail', pk=mockup.pk)
    else:
        form = PackageMockupForm()
    return render(request, 'projects/mockups/form.html', {'form': form})

@login_required
def mockup_detail(request, pk):
    mockup = get_object_or_404(PackageMockup, pk=pk, owner=request.user)
    return render(request, 'projects/mockups/detail.html', {'mockup': mockup})

@login_required
def mockup_delete(request, pk):
    mockup = get_object_or_404(PackageMockup, pk=pk, owner=request.user)
    if request.method == 'POST':
        mockup.delete()
        messages.success(request, 'Mockup deleted.')
        return redirect('projects:mockup_list')
    return render(request, 'projects/mockups/confirm_delete.html', {'mockup': mockup})

@login_required
def mockup_update(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    mockup = get_object_or_404(PackageMockup, pk=pk, owner=request.user)
    def get_float(name, default):
        try:
            return float(request.POST.get(name, default))
        except Exception:
            return default
    mockup.design_pos_x = get_float('design_pos_x', mockup.design_pos_x)
    mockup.design_pos_y = get_float('design_pos_y', mockup.design_pos_y)
    mockup.design_scale = get_float('design_scale', mockup.design_scale)
    mockup.design_rotation = get_float('design_rotation', mockup.design_rotation)
    old_mask_path = mockup.mask_image.path if getattr(mockup, 'mask_image') and mockup.mask_image else None
    old_design_path = mockup.design_image.path if getattr(mockup, 'design_image') and mockup.design_image else None
    if request.POST.get('clear_mask') == '1':
        mockup.mask_image = None
    add_bytes = _incoming_files_size(request.FILES, ['mask_image', 'design_image', 'container_image'])
    if _would_exceed_quota(request.user, add_bytes):
        return JsonResponse({'error': 'Quota exceeded'}, status=400)
    if 'mask_image' in request.FILES and request.FILES['mask_image']:
        processed = _process_image_strip_metadata(request.FILES['mask_image'])
        if processed:
            content, new_name = processed
            mockup.mask_image.save(new_name, content, save=False)
    mop = request.POST.get('mask_opacity')
    mfe = request.POST.get('mask_feather')
    miv = request.POST.get('mask_invert')
    if mop is not None:
        try:
            mockup.mask_opacity = float(mop)
        except Exception:
            pass
    if mfe is not None:
        try:
            mockup.mask_feather = float(mfe)
        except Exception:
            pass
    if miv is not None:
        mockup.mask_invert = miv in ['1', 'true', 'True', 'on']
    if 'design_image' in request.FILES and request.FILES['design_image']:
        processed = _process_image_strip_metadata(request.FILES['design_image'])
        if processed:
            content, new_name = processed
            mockup.design_image.save(new_name, content, save=False)
    if 'container_image' in request.FILES and request.FILES['container_image']:
        processed = _process_image_strip_metadata(request.FILES['container_image'])
        if processed:
            content, new_name = processed
            mockup.container_image.save(new_name, content, save=False)
    mockup.save()
    compose_mockup_image(mockup)
    url = mockup.generated_image.url if mockup.generated_image else ''
    return JsonResponse({'ok': True, 'generated_image': url})