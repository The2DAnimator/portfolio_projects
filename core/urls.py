from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('help/', views.help_center, name='help'),
    path('contact/', views.contact, name='contact'),
    path('api/messages/<int:user_id>/', views.get_conversation, name='get_conversation'),
    path('api/messages/<int:user_id>/send/', views.send_message, name='send_message'),
    path('api/device/location/', views.api_device_location, name='api_device_location'),
    path('control/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('control/storage/', views.admin_storage, name='admin_storage'),
    path('control/analytics/', views.admin_analytics, name='admin_analytics'),
    path('control/users/<int:user_id>/toggle-active/', views.admin_user_toggle_active, name='admin_user_toggle_active'),
    path('control/users/<int:user_id>/toggle-staff/', views.admin_user_toggle_staff, name='admin_user_toggle_staff'),
    path('control/users/', views.admin_users, name='admin_users'),
    path('control/users/bulk/', views.admin_users_bulk, name='admin_users_bulk'),
    # Projects management
    path('control/projects/', views.admin_projects, name='admin_projects'),
    path('control/projects/bulk/', views.admin_projects_bulk, name='admin_projects_bulk'),
    path('control/projects/<int:project_id>/publish/', views.admin_project_publish, name='admin_project_publish'),
    path('control/projects/<int:project_id>/unpublish/', views.admin_project_unpublish, name='admin_project_unpublish'),
    path('control/projects/<int:project_id>/delete/', views.admin_project_delete, name='admin_project_delete'),
    # Categories CRUD
    path('control/categories/', views.admin_categories, name='admin_categories'),
    path('control/categories/create/', views.admin_category_create, name='admin_category_create'),
    path('control/categories/<int:category_id>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('control/categories/<int:category_id>/delete/', views.admin_category_delete, name='admin_category_delete'),
]