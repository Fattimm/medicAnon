from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.conf.urls.static import static
from django.conf import settings
from django.urls import path, include

urlpatterns = [
    path("anonymize/", views.anonymize, name="anonymize"),
    path("anonymize/result/<int:fichier_id>/", views.anonymize_result, name="anonymize_result"),
    path("download/<int:fichier_id>/", views.download_anonymized, name="download_anonymized"),
    path("share/<int:fichier_id>/", views.share_anonymized, name="share_anonymized"),
    path("metrics/", views.metrics, name="metrics"),
    path("compliance/", views.compliance_report, name="compliance_report"),
    path("export/csv/", views.export_fichiers_csv, name="export_fichiers_csv"),
    path("public-hub/", views.public_hub, name="public_hub"),
    path('download/public/<int:fichier_id>/', views.download_public_file, name='download_public_file'),
    path("", views.accueil, name="accueil"),
    path("register/", views.register_view, name="register"),
    path('login/', auth_views.LoginView.as_view(template_name='medicanon/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path("manage-users/", views.manage_users, name="manage_users"),
    path('api/preview/<int:fichier_id>/', views.file_preview_api, name='file_preview_api'),

]

