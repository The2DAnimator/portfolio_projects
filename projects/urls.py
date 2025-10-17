from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('public/', views.public_projects, name='public_projects'),
    path('create/', views.project_create, name='project_create'),
    path('view/<int:pk>/', views.project_view, name='project_view'),
    path('<int:pk>/', views.project_detail, name='project_detail'),
    path('<int:pk>/update/', views.project_update, name='project_update'),
    path('<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('<int:project_pk>/add-image/', views.add_project_image, name='add_project_image'),
    path('<int:project_pk>/add-file/', views.add_project_file, name='add_project_file'),
    path('api/projects/<int:project_id>/toggle-like/', views.toggle_like, name='toggle_like'),
    # Mockups
    path('mockups/', views.mockup_list, name='mockup_list'),
    path('mockups/create/', views.mockup_create, name='mockup_create'),
    path('mockups/<int:pk>/', views.mockup_detail, name='mockup_detail'),
    path('mockups/<int:pk>/update/', views.mockup_update, name='mockup_update'),
    path('mockups/<int:pk>/delete/', views.mockup_delete, name='mockup_delete'),
]