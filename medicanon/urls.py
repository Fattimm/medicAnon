from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from . import views
from django.conf.urls.static import static
from django.conf import settings
from django.urls import path, include

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('public/', views.public_hub, name='public_hub'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='medicanon/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('export-fichiers/', views.export_fichiers_csv, name='export_fichiers'),
    path('anonymize/', views.anonymize, name='anonymize'),
    path('anonymize/result/<int:fichier_id>/', views.anonymize_result, name='anonymize_result'),
    path('share_anonymized/<int:fichier_id>/', views.share_anonymized, name='share_anonymized'),
    path('metrics/', views.metrics, name='metrics'),
    path('compliance-report/', views.compliance_report, name='compliance_report'),
    path('import/', views.import_fichier, name='import_fichier'),
    path('download/<int:fichier_id>/', views.telecharger_fichier, name='telecharger_fichier'),
    path('download/<int:fichier_id>/', views.telecharger_fichier, name='download_public_file'),
    path('download_anonymized/<int:fichier_id>/', views.download_anonymized, name='download_anonymized'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)