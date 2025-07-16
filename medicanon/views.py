import csv
import io
import hashlib
import spacy
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
import PyPDF2
import pdfplumber
from docx import Document
from .models import Utilisateur, Fichier, Historique, Métriques, RapportConformité, Données, RègleAnonymisation
import pandas as pd
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage



# Charger le modèle spaCy une seule fois
nlp = spacy.load("fr_core_news_sm")

# Listes séparées de prénoms et noms sénégalais
SENEGALESE_FIRSTNAMES = [
    "Awa", "Fatou", "Pape", "Fatoumata", "Fatimata", "Fatima", "Memedou", "Mouhamed", "Modou", "Mouhamadou", "Cheikh", "Amadou", "Omar", "Oumar", "Aminata", "Khadidiatou", "Mariama", "Ousmane", "Ibrahima", "Abdoulaye", "Khadija"
]
SENEGALESE_LASTNAMES = [
    "Diouf", "Sow", "Ndiaye", "Fall", "Diop", "Ba", "Sarr", "Gaye", "Mbengue", "Thiam",
    "Faye", "Diallo", "Dia", "Kandji", "Niang", "Ngom", "Cissé", "Sy", "Mbacke", "Seck", "Tall", "Demba"
]

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'Visiteur'  # role forcé
            user.email = request.POST.get('email')
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.save()
            login(request, user)
            return redirect('public_hub')
    else:
        form = UserCreationForm()
    return render(request, 'medicanon/register.html', {'form': form})

def accueil(request):
    return render(request, 'medicanon/accueil.html')

def redirect_after_login(request):
    user = request.user
    if user.is_authenticated:
        if user.role in ['Agent', 'Administrateur']:
            return redirect('base')
        else:
            return redirect('accueil')
    return redirect('login')

@login_required
def manage_users(request):
    return render(request, 'medicanon/manage_users.html')

def extract_text_from_file(file):
    file_extension = file.name.split('.')[-1].lower()
    text = ""
    file.seek(0)
    if file_extension == 'csv':
        decoded_file = file.read().decode('utf-8', errors='ignore')
        text = decoded_file
    elif file_extension == 'pdf':
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif file_extension == 'docx':
        doc = Document(io.BytesIO(file.read()))
        for para in doc.paragraphs:
            text += para.text + "\n"
    return text

def detect_ipi_fields(fichier):
    ipi_fields = []
    text = extract_text_from_file(fichier.fichier)
    if not text:
        return ipi_fields
    file_extension = fichier.fichier.name.split('.')[-1].lower()
    if file_extension in ['pdf', 'docx']:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ in ['PER', 'LOC'] or any(fname in ent.text for fname in SENEGALESE_FIRSTNAMES) or any(lname in ent.text for lname in SENEGALESE_LASTNAMES):
                ipi_fields.append(f"Champ_{hash(ent.text) % 10 + 1}")
        return list(set(ipi_fields))
    fichier.fichier.seek(0)
    decoded_file = fichier.fichier.read().decode('utf-8', errors='ignore')
    csv_reader = csv.reader(io.StringIO(decoded_file))
    headers = next(csv_reader, [])
    for header in headers:
        doc = nlp(header.lower())
        if any(ent.label_ in ['PER', 'LOC', 'ORG'] for ent in doc.ents) or \
           any(fname.lower() in header.lower() for fname in SENEGALESE_FIRSTNAMES) or \
           any(lname.lower() in header.lower() for lname in SENEGALESE_LASTNAMES) or \
           any(kw.lower() in header.lower() for kw in ['patient', 'nom', 'prenom', 'adresse', 'email', 'telephone', 'date_naissance']):
            ipi_fields.append(header)
    for i, row in enumerate(csv_reader):
        if i >= 5:
            break
        for cell in row:
            doc = nlp(cell.lower())
            if any(ent.label_ in ['PER', 'LOC'] for ent in doc.ents) or \
               any(fname.lower() in cell.lower() for fname in SENEGALESE_FIRSTNAMES) or \
               any(lname.lower() in cell.lower() for lname in SENEGALESE_LASTNAMES):
                header_idx = row.index(cell)
                if headers[header_idx] not in ipi_fields:
                    ipi_fields.append(headers[header_idx])
    return list(set(ipi_fields))

def calculate_sensitivity_score(fields):
    sensitivity_weights = {'nom': 30, 'prenom': 25, 'adresse': 20, 'date_naissance': 15, 'email': 10, 'patient': 20}
    total_weight = sum(sensitivity_weights.get(field.lower(), 0) for field in fields)
    return min(100, total_weight)

def anonymize_data(headers, rows, selected_ipi, methods):
    anonymized_rows = []
    colonnes_anonymisees = 0
    for row in rows:
        new_row = []
        for i, cell in enumerate(row):
            header = headers[i].lower() if headers else f"champ_{i+1}"
            if header in [h.lower() for h in selected_ipi]:
                method = methods.get(headers[i] if headers else f"champ_{i+1}", 'none')
                if method == 'suppression':
                    new_row.append("")
                    colonnes_anonymisees += 1
                elif method == 'pseudonymisation':
                    new_row.append(f"user_{hash(cell) % 10000}")
                    colonnes_anonymisees += 1
                elif method == 'generalisation':
                    new_row.append("Tranche")
                    colonnes_anonymisees += 1
                elif method == 'hachage':
                    new_row.append(hashlib.sha256(cell.encode()).hexdigest())
                    colonnes_anonymisees += 1
                else:
                    new_row.append(cell)
            else:
                new_row.append(cell)
        anonymized_rows.append(new_row)
    return anonymized_rows


@login_required
def anonymize(request):
    step = int(request.GET.get('step', 1))
    fichier_id = request.GET.get('fichier_id')  # Récupère l'ID depuis l'URL
    uploaded_file = request.session.get('uploaded_file')  # Récupère depuis la session
    fichiers = Fichier.objects.filter(utilisateur=request.user, statut__in=['Importé', 'En cours'])
    methodes = ['Suppression', 'Pseudonymisation', 'Généralisation', 'Hachage']
    ipi_fields = ['nom', 'prenom', 'date_naissance', 'adresse', 'email', 'telephone']  # Sera remplacé dynamiquement
    sensitivity_score = 0
    lignes_traitees = 0
    colonnes_anonymisees = 0
    taux_anonymisation = 0
    score_securite = 0
    analyse_risques = "Risque faible"
    conformite = "Conforme RGPD/CDP"
    recommandations = "Conserver dans un environnement sécurisé"
    headers = None
    original = None
    anonymized = None

    # Récupérer les informations du fichier si fichier_id existe et détecter les champs IPI
    if fichier_id:
        try:
            fichier_instance = Fichier.objects.get(id=fichier_id, utilisateur=request.user)
            uploaded_file = {
                'nom_fichier': fichier_instance.nom_fichier,
                'extension': fichier_instance.nom_fichier.split('.')[-1].lower(),
                'id': fichier_id
            }
            request.session['uploaded_file'] = uploaded_file  # Mettre à jour la session
            # Détecter les champs IPI dynamiquement
            ipi_fields = detect_ipi_fields(fichier_instance)
            sensitivity_score = calculate_sensitivity_score(ipi_fields)
        except Fichier.DoesNotExist:
            messages.error(request, "Fichier introuvable.")
            if 'uploaded_file' in request.session:
                del request.session['uploaded_file']  # Supprimer si invalide
            return redirect('anonymize')

    if request.method == 'POST':
        if 'fichier' in request.FILES:
            uploaded_file = request.FILES['fichier']
            file_extension = uploaded_file.name.split('.')[-1].lower()
            if file_extension not in ['csv', 'pdf', 'docx']:
                messages.error(request, "Format non supporté. Utilisez CSV, PDF ou DOCX.")
                return redirect('anonymize')
            with transaction.atomic():
                fichier_instance = Fichier.objects.create(
                    fichier=uploaded_file,
                    nom_fichier=uploaded_file.name,
                    statut='Importé',
                    utilisateur=request.user
                )
                fichier_id = str(fichier_instance.id)  # Stocke l'ID du fichier importé
            uploaded_file = {'nom_fichier': uploaded_file.name, 'extension': file_extension, 'id': fichier_id}
            request.session['uploaded_file'] = uploaded_file  # Stocker dans la session
            messages.success(request, "Fichier importé avec succès.")
            # Correction : Utiliser reverse avec les paramètres de requête
            url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
            return redirect(url)
        elif 'from_config' in request.POST:
            fichier_id = request.POST.get('fichier_id')
            if not fichier_id:
                messages.error(request, "Aucun fichier sélectionné.")
                url = reverse('anonymize') + '?step=2'
                return redirect(url)
            
            # Récupérer les champs IPI sélectionnés et les méthodes
            selected_ipi = request.POST.getlist('ipi_fields')
            # Vérifier qu'au moins un champ IPI est sélectionné
            if not selected_ipi:
                messages.error(request, "Veuillez sélectionner au moins un champ IPI à anonymiser.")
                url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                return redirect(url)

            # Vérifier que des méthodes sont sélectionnées
            methods = {field: request.POST.get(f'method_{field}', 'none') for field in selected_ipi}
            if all(method == 'none' for method in methods.values()):
                messages.error(request, "Veuillez sélectionner une méthode d'anonymisation pour au moins un champ.")
                url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                return redirect(url)
            
            # Stocker les configurations dans la session
            request.session['selected_ipi'] = selected_ipi
            request.session['methods'] = methods
            
            # Traiter le fichier CSV
            try:
                fichier_instance = Fichier.objects.get(id=fichier_id, utilisateur=request.user)
                file_extension = fichier_instance.nom_fichier.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    fichier_instance.fichier.seek(0)
                    decoded_file = fichier_instance.fichier.read().decode('utf-8', errors='ignore')
                    csv_reader = csv.reader(io.StringIO(decoded_file))
                    headers = next(csv_reader, [])
                    original = list(csv_reader)
                    
                    # Vérifier que le fichier n'est pas vide
                    if not headers:
                        messages.error(request, "Le fichier CSV semble vide ou mal formaté.")
                        url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                        return redirect(url)
                    
                    # Anonymiser les données
                    anonymized = anonymize_data(headers, original, selected_ipi, methods)
                    
                    # Calculer les métriques
                    lignes_traitees = len(original)
                    colonnes_anonymisees = len(selected_ipi)
                    taux_anonymisation = (colonnes_anonymisees / len(headers)) * 100 if headers else 0
                    score_securite = min(100, taux_anonymisation + calculate_sensitivity_score(selected_ipi))
                    
                    # Stocker toutes les données dans la session
                    request.session['headers'] = headers
                    request.session['original'] = original
                    request.session['anonymized'] = anonymized
                    request.session['lignes_traitees'] = lignes_traitees
                    request.session['colonnes_anonymisees'] = colonnes_anonymisees
                    request.session['taux_anonymisation'] = taux_anonymisation
                    request.session['score_securite'] = score_securite
                    
                    # Debugging - vérifier que les données sont bien stockées
                    print(f"DEBUG - Données stockées en session:")
                    print(f"  - selected_ipi: {len(selected_ipi)} éléments")
                    print(f"  - methods: {len(methods)} éléments")
                    print(f"  - headers: {len(headers)} éléments")
                    print(f"  - original: {len(original)} lignes")
                    print(f"  - anonymized: {len(anonymized)} lignes")
                    
                    # Redirection vers l'étape 3
                    url = reverse('anonymize') + f'?step=3&fichier_id={fichier_id}'
                    return redirect(url)
                else:
                    messages.error(request, "Seuls les fichiers CSV sont supportés pour l'anonymisation pour le moment.")
                    url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                    return redirect(url)
                    
            except Fichier.DoesNotExist:
                messages.error(request, "Fichier introuvable.")
                return redirect('anonymize')
            except Exception as e:
                messages.error(request, f"Erreur lors du traitement du fichier: {str(e)}")
                url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                return redirect(url)
        # Dans votre fonction anonymize, remplacez la condition 'from_anonymize' par cette version corrigée :
        elif 'from_anonymize' in request.POST:
            fichier_id = request.POST.get('fichier_id')
            if not fichier_id:
                messages.error(request, "Aucun fichier sélectionné.")
                return redirect('anonymize')
            
            try:
                fichier_instance = Fichier.objects.get(id=fichier_id, utilisateur=request.user)
                
                # Récupérer les données depuis la session
                selected_ipi = request.session.get('selected_ipi', [])
                methods = request.session.get('methods', {})
                headers = request.session.get('headers', [])
                original = request.session.get('original', [])
                anonymized = request.session.get('anonymized', [])
                
                # Vérifications des données manquantes...
                missing_data = []
                if not selected_ipi:
                    missing_data.append("selected_ipi")
                if not methods:
                    missing_data.append("methods")
                if not headers:
                    missing_data.append("headers")
                if not original:
                    missing_data.append("original")
                if not anonymized:
                    missing_data.append("anonymized")
                    
                if missing_data:
                    messages.error(request, f"Données d'anonymisation manquantes: {', '.join(missing_data)}. Veuillez recommencer.")
                    url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                    return redirect(url)
                
                # NOUVEAU : Créer le fichier anonymisé
                anonymized_content = io.StringIO()
                writer = csv.writer(anonymized_content)
                
                # Écrire les en-têtes
                if headers:
                    writer.writerow(headers)
                
                # Écrire les données anonymisées
                for row in anonymized:
                    writer.writerow(row)
                
                # Sauvegarder le fichier anonymisé
                anonymized_filename = f"anonymized_{fichier_instance.nom_fichier}"
                anonymized_file_content = ContentFile(anonymized_content.getvalue().encode('utf-8'))
                
                # Sauvegarder le fichier anonymisé dans le système de fichiers
                anonymized_file_path = default_storage.save(f'fichiers_anonymises/{anonymized_filename}', anonymized_file_content)
                
                # Mettre à jour le fichier avec le chemin du fichier anonymisé
                fichier_instance.statut = 'Anonymisé'
                fichier_instance.fichier_anonymise = anonymized_file_path  # Nouveau champ à ajouter au modèle
                fichier_instance.save()
                
                # Créer un enregistrement dans l'historique
                historique = Historique.objects.create(
                    fichier=fichier_instance,
                    utilisateur=request.user,
                    partage=False
                )
                
                # Créer les métriques
                lignes_traitees = len(original)
                colonnes_anonymisees = len(selected_ipi)
                taux_anonymisation = (colonnes_anonymisees / len(headers)) * 100 if headers else 0
                score_securite = min(100, taux_anonymisation + calculate_sensitivity_score(selected_ipi))
                
                Métriques.objects.create(
                    historique=historique,
                    lignes_traitees=lignes_traitees,
                    colonnes_anonymisees=colonnes_anonymisees,
                    taux_anonymisation=taux_anonymisation,
                    score_securite=score_securite
                )
                
                # Stocker les métriques dans la session pour l'étape 4
                request.session['lignes_traitees'] = lignes_traitees
                request.session['colonnes_anonymisees'] = colonnes_anonymisees
                request.session['taux_anonymisation'] = taux_anonymisation
                request.session['score_securite'] = score_securite
                
                messages.success(request, "Anonymisation terminée avec succès.")
                
                # Rediriger vers l'étape 4
                url = reverse('anonymize') + f'?step=4&fichier_id={fichier_id}'
                return redirect(url)
                
            except Fichier.DoesNotExist:
                messages.error(request, "Fichier introuvable.")
                return redirect('anonymize')
            except Exception as e:
                messages.error(request, f"Erreur lors de la sauvegarde du fichier anonymisé: {str(e)}")
                url = reverse('anonymize') + f'?step=2&fichier_id={fichier_id}'
                return redirect(url)
        elif 'fichier_id' in request.POST and 'from_export' in request.POST:
            fichier_id = request.POST.get('fichier_id')
            format_export = request.POST.get('format')
            share_hub = request.POST.get('share_hub', False)
            
            # Stocker les paramètres d'export
            request.session['format_export'] = format_export
            request.session['share_hub'] = share_hub
            
            # Logique d'export (à implémenter)
            url = reverse('anonymize') + f'?step=4&fichier_id={fichier_id}'
            return redirect(url)

    # Récupérer les données depuis la session si elles existent
    if step >= 3:
        headers = request.session.get('headers', [])
        original = request.session.get('original', [])
        anonymized = request.session.get('anonymized', [])
        lignes_traitees = request.session.get('lignes_traitees', 0)
        colonnes_anonymisees = request.session.get('colonnes_anonymisees', 0)
        taux_anonymisation = request.session.get('taux_anonymisation', 0)
        score_securite = request.session.get('score_securite', 0)

    # Contexte pour toutes les étapes
    context = {
        'step': step,
        'uploaded_file': uploaded_file,
        'fichiers': fichiers,
        'methodes': methodes,
        'ipi_fields': ipi_fields,
        'sensitivity_score': sensitivity_score,
        'lignes_traitees': lignes_traitees,
        'colonnes_anonymisees': colonnes_anonymisees,
        'taux_anonymisation': taux_anonymisation,
        'score_securite': score_securite,
        'analyse_risques': analyse_risques,
        'conformite': conformite,
        'recommandations': recommandations,
        'fichier_id': fichier_id,
        'headers': headers,
        'original': original,
        'anonymized': anonymized,
    }
    return render(request, 'medicanon/anonymize.html', context)


@login_required
def anonymize_result(request, fichier_id):
    fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
    headers = request.session.get('headers', [])
    original = request.session.get('original', [])
    anonymized = request.session.get('anonymized', [])
    return render(request, 'medicanon/anonymize_result.html', {
        'fichier': fichier,
        'headers': headers,
        'original': original,
        'anonymized': anonymized,
    })

@login_required
def share_anonymized(request, fichier_id):
    fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
    fichier.partage = True
    fichier.save()
    messages.success(request, "Fichier partagé avec succès.")
    return redirect('anonymize_result', fichier_id=fichier.id)

@login_required
def download_anonymized(request, fichier_id):
    fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
    anonymized = request.session.get('anonymized', [])
    headers = request.session.get('headers', [])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename=anonymized_{fichier.nom_fichier}'
    writer = csv.writer(response)
    if headers:
        writer.writerow(headers)
    for row in anonymized:
        writer.writerow(row)
    return response

@login_required
def metrics(request):
    historiques = Historique.objects.filter(utilisateur=request.user)
    metriques = Métriques.objects.filter(historique__in=historiques)
    return render(request, 'medicanon/metrics.html', {'metriques': metriques})

@login_required
def compliance_report(request):
    historiques = Historique.objects.filter(utilisateur=request.user)
    rapports = RapportConformité.objects.filter(historique__in=historiques)
    return render(request, 'medicanon/compliance_report.html', {'rapports': rapports})

def custom_logout(request):
    logout(request)
    return redirect('accueil')

@login_required
def import_fichier(request):
    fichiers = Fichier.objects.all().order_by('-date_import')
    search_query = request.GET.get('search', '').strip()
    statut_filter = request.GET.get('statut', '').strip()
    if search_query:
        fichiers = fichiers.filter(nom_fichier__icontains=search_query)
    if statut_filter:
        fichiers = fichiers.filter(statut=statut_filter)
    if request.method == 'POST' and request.FILES.get('fichier'):
        uploaded_file = request.FILES['fichier']
        fichier_instance = Fichier.objects.create(
            fichier=uploaded_file,
            nom_fichier=uploaded_file.name,
            statut='Importé',
            utilisateur=request.user
        )
        return redirect('import_fichier')
    paginator = Paginator(fichiers, 5)
    page_number = request.GET.get('page')
    fichiers_page = paginator.get_page(page_number)
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'medicanon/_fichiers_table.html', {'fichiers': fichiers_page})
    return render(request, 'medicanon/import.html', {
        'fichiers': fichiers_page,
        'search_query': search_query,
        'statut_filter': statut_filter
    })

@login_required
def delete_fichier(request, pk):
    fichier = get_object_or_404(Fichier, pk=pk)
    fichier.delete()
    fichiers = Fichier.objects.all().order_by('-date_import')
    paginator = Paginator(fichiers, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'medicanon/_fichiers_table.html', {'fichiers': page_obj})


@login_required
def telecharger_fichier(request, fichier_id):  
    fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
    
    # Vérifier si le fichier anonymisé existe
    if fichier.fichier_anonymise and fichier.statut == 'Anonymisé':
        return FileResponse(
            fichier.fichier_anonymise.open('rb'), 
            as_attachment=True, 
            filename=f"anonymized_{fichier.nom_fichier}"
        )
    
    # Fallback : générer le CSV depuis la session (si encore disponible)
    anonymized = request.session.get('anonymized', [])
    headers = request.session.get('headers', [])
    
    if not anonymized:
        messages.error(request, "Fichier anonymisé non disponible. Veuillez relancer l'anonymisation.")
        return redirect('anonymize')
    
    # Générer le CSV à la volée
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename=anonymized_{fichier.nom_fichier}'
    writer = csv.writer(response)
    
    if headers:
        writer.writerow(headers)
    for row in anonymized:
        writer.writerow(row)
    
    return response

@login_required
def export_fichiers_csv(request):
    fichiers = Fichier.objects.all().order_by('-date_import')
    search_query = request.GET.get('search')
    statut_filter = request.GET.get('statut')
    if search_query:
        fichiers = fichiers.filter(nom_fichier__icontains=search_query)
    if statut_filter:
        fichiers = fichiers.filter(statut=statut_filter)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="fichiers_medic_anon.csv"'
    writer = csv.writer(response)
    writer.writerow(['Nom Fichier', 'Date Import', 'Statut', 'Utilisateur'])
    for fichier in fichiers:
        writer.writerow([
            fichier.nom_fichier,
            fichier.date_import.strftime("%d/%m/%Y %H:%M"),
            fichier.statut,
            fichier.utilisateur.username
        ])
    return response

def public_hub(request):
    fichiers_anonymises = Fichier.objects.filter(statut='Anonymisé')
    return render(request, 'medicanon/public_hub.html', {'fichiers': fichiers_anonymises})

