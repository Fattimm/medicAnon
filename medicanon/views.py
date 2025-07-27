import csv
import io
import hashlib
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from .models import Utilisateur, Fichier, Historique, Métriques, RapportConformité
import pandas as pd
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import re
from datetime import datetime
import secrets
from django.views.decorators.http import require_GET
from .forms import CustomUserCreationForm
from django.core.exceptions import PermissionDenied
from django.utils import timezone 
import pickle
import gzip
from django.utils.text import slugify
import unicodedata



# Dictionnaires étendus pour le Sénégal
SENEGALESE_FIRSTNAMES = [
    "Awa", "Fatou", "Pape", "Fatoumata", "Fatimata", "Fatima", "Memedou", 
    "Mouhamed", "Modou", "Mouhamadou", "Cheikh", "Amadou", "Omar", "Oumar", 
    "Aminata", "Khadidiatou", "Mariama", "Ousmane", "Ibrahima", "Abdoulaye", 
    "Khadija", "Aissatou", "Adama", "Seynabou", "Sokhna", "Binta", "Ndèye",
    "Moussa", "Mamadou", "Aliou", "Lamine", "Saliou", "Babacar"
]

SENEGALESE_LASTNAMES = [
    "Diouf", "Sow", "Ndiaye", "Fall", "Diop", "Ba", "Sarr", "Gaye", "Mbengue", 
    "Thiam", "Faye", "Diallo", "Dia", "Kandji", "Niang", "Ngom", "Cissé", "Sy", 
    "Mbacke", "Seck", "Tall", "Demba", "Kane", "Sané", "Samb", "Camara", "Touré"
]

# Patterns de détection améliorés
MEDICAL_PATTERNS = {
    # === DONNÉES D'IDENTITÉ CLASSIQUES ===
    'nom': r'\b(nom|name|lastname|surname|family)\b',
    'prenom': r'\b(prenom|firstname|given)\b',
    'patient_id': r'\b(patient|id|identifiant)[\s_-]*(id|num|numero|number)?\b',
    'phone': r'\b(telephone|phone|mobile|tel|gsm)\b',
    'email': r'\b(email|mail|courriel)\b',
    'date_naissance': r'\b(date[\s_-]*naissance|birth[\s_-]*date|ddn|dob|age)\b',
    'address': r'\b(adresse|address|domicile|residence)\b',
    'cni': r'\b(cni|carte[\s_-]*identite|passport|passeport)\b',
    
    # === NOUVEAUX PATTERNS MÉDICAUX ===
    # Diagnostic et pathologies
    'diagnostic': r'\b(diagnostic|pathologie|maladie|disease|illness|condition|syndrome|trouble)\b',
    'symptoms': r'\b(symptome|symptom|signe|manifestation)\b',
    'treatment': r'\b(traitement|treatment|medicament|medication|prescription|ordonnance)\b',
    
    # Données biométriques et physiologiques
    'blood_group': r'\b(groupe[\s_-]*sanguin|blood[\s_-]*group|rhesus|rh)\b',
    'weight': r'\b(poids|weight|masse)\b',
    'height': r'\b(taille|height|size)\b',
    'blood_pressure': r'\b(tension|pressure|systolique|diastolique)\b',
    'temperature': r'\b(temperature|fievre|fever)\b',
    
    # Données démographiques sensibles
    'gender': r'\b(sexe|genre|gender|sex)\b',
    'religion': r'\b(religion|confession|culte)\b',
    'ethnicity': r'\b(ethnie|race|origine|tribu)\b',
    
    # Données administratives médicales
    'medical_number': r'\b(numero[\s_-]*medical|medical[\s_-]*id|dossier[\s_-]*medical)\b',
    'insurance': r'\b(assurance|mutuelle|couverture|insurance)\b',
    'doctor': r'\b(medecin|docteur|doctor|praticien)\b',
    'hospital': r'\b(hopital|hospital|clinique|centre[\s_-]*sante)\b',
    
    # Données financières médicales
    'medical_cost': r'\b(cout|cost|prix|tarif|facture|bill)\b',
    
    # Spécificités sénégalaises
    'wolof_names': r'\b(anta|modou|fatou|pape|cheikh|aminata|moussa|binta)\b',
    'senegal_locations': r'\b(dakar|thies|kaolack|saint[\s_-]*louis|ziguinchor|diourbel|tambacounda|kolda|matam|sedhiou|kaffrine|kedougou|fatick|louga)\b',
    'age': r'\b(a|â|à|ä|á|ã|å|æ)g(e|é|è|ê|ë)?\b',
    'date_consultation': r'\b(date[\s_-]*consultation|consultation[\s_-]*date)\b',
    'prescription': r'\b(prescription|ordonnance|treatment|traitement|medicament|medication)\b',
    'commune': r'\b(commune|quartier|ville|localite|localité)\b',
    'hopital': r'\b(hopital|hôpital|centre[\s_-]*sante|clinique|poste[\s_-]*sante)\b',
    'numero_secu': r'\b(numero[\s_-]*secu|nir|num[\s_-]*secu|securite[\s_-]*sociale|nss)\b',
    'lieu_naissance': r'\b(lieu[\s_-]*naissance|ville[\s_-]*naissance|pays[\s_-]*naissance)\b',
    'nationalite': r'\b(nationalite|nationalité|pays[\s_-]*origine)\b',
    'code_postal': r'\b(code[\s_-]*postal|cp|zip[\s_-]*code)\b',
    'pays': r'\b(pays|country|nation)\b',
    'contact_urgence': r'\b(contact[\s_-]*urgence|proche|urgence|famille)\b',
    'situation_familiale': r'\b(situation[\s_-]*familiale|statut[\s_-]*marital|marital|familial)\b',
    'date_hospitalisation': r'\b(date[\s_-]*hospitalisation|date[\s_-]*entree|entree|admission)\b',
    'date_sortie': r'\b(date[\s_-]*sortie|sortie|discharge)\b',
    'service': r'\b(service|departement|specialite|spécialité|unite|unité)\b',
    'antecedents': r'\b(antecedents|antécédents|historique[\s_-]*medical|medical[\s_-]*history)\b',
    'allergies': r'\b(allergies|allergie|allergique|intolerance)\b',
    'resultats': r'\b(resultats|résultats|analyses|examens|tests|resultat|résultat)\b',
    'numero_chambre': r'\b(numero[\s_-]*chambre|chambre|lit|room|bed)\b',
    'tension': r'\b(tension|pression[\s_-]*arterielle|blood[\s_-]*pressure|tension[\s_-]*arterielle)\b',
    'temperature': r'\b(temperature|température|fievre|fever)\b',
    'profession': r'\b(profession|metier|métier|job|travail|occupation)\b',
    'employeur': r'\b(employeur|entreprise|company|societe|société)\b',
    'nombre_enfants': r'\b(nombre[\s_-]*enfants|enfants|children|nb[\s_-]*enfants)\b',
    'mutuelle': r'\b(mutuelle|assurance|insurance|couverture)\b',
    'cout': r'\b(cout|coût|prix|cost|facture|bill|tarif)\b',
}

ENHANCED_SENSITIVITY_WEIGHTS = {
    # === DONNÉES DE SANTÉ (Article 9 RGPD) - SENSIBILITÉ MAXIMALE ===
    'diagnostic': 50,      # LE PLUS SENSIBLE
    'pathologie': 50,
    'symptoms': 45,
    'treatment': 45,
    'blood_group': 40,     # Données biométriques
    'medical_number': 40,
    'blood_pressure': 35,
    'weight': 30,
    'height': 25,
    'temperature': 25,
    
    # === DONNÉES D'IDENTITÉ (Article 6 RGPD) ===
    'cni': 40,
    'nom': 35,
    'prenom': 30,
    'date_naissance': 30,
    'adresse': 25,
    'telephone': 20,
    'email': 20,
    'patient_id': 25,
    
    # === DONNÉES DÉMOGRAPHIQUES SENSIBLES (Article 9) ===
    'gender': 25,         # Ajouté pour "sexe"
    'religion': 30,
    'ethnicity': 35,
    
    # === DONNÉES ADMINISTRATIVES ===
    'insurance': 25,
    'doctor': 20,
    'hospital': 15,
    'medical_cost': 20,
    
    # === DONNÉES GÉOGRAPHIQUES/CULTURELLES ===
    'wolof_names': 35,
    'senegal_locations': 15,
    'age': 20,
    'date_consultation': 20,
    'prescription': 40,
    'commune': 15,
    'hopital': 20,
    'numero_secu': 45,
    'lieu_naissance': 25,
    'nationalite': 20,
    'code_postal': 20,
    'pays': 15,
    'contact_urgence': 30,
    'situation_familiale': 20,
    'date_hospitalisation': 25,
    'date_sortie': 25,
    'service': 20,
    'antecedents': 40,
    'allergies': 35,
    'resultats': 45,
    'numero_chambre': 15,
    'tension': 30,
    'temperature': 25,
    'profession': 20,
    'employeur': 20,
    'nombre_enfants': 20,
    'mutuelle': 25,
    'cout': 20,
}


# Nouvelle fonction uniquement CSV
def detect_ipi_fields_csv_only(fichier):
    """
    Détection IPI améliorée avec support des champs médicaux
    """
    ipi_fields = []
    
    if not fichier.nom_fichier.lower().endswith('.csv'):
        return ipi_fields
    
    try:
        fichier.fichier.seek(0)
        decoded_file = fichier.fichier.read().decode('utf-8', errors='ignore')
        csv_reader = csv.reader(io.StringIO(decoded_file))
        headers = next(csv_reader, [])
        
        # === ÉTAPE 1: DÉTECTION PAR PATTERNS ===
        detected_by_pattern = []
        for header in headers:
            # Normalisation : minuscules + suppression des accents
            header_norm = unicodedata.normalize('NFKD', header).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
            for pattern_name, pattern in MEDICAL_PATTERNS.items():
                if re.search(pattern, header_norm, re.IGNORECASE):
                    if header not in detected_by_pattern:
                        detected_by_pattern.append(header)
                        print(f"✅ '{header}' détecté par pattern '{pattern_name}' (normalisé: '{header_norm}')")
                    break
        
        # === ÉTAPE 2: VALIDATION PAR CONTENU ===
        sample_rows = []
        for i, row in enumerate(csv_reader):
            if i >= 10:  # Analyser 10 lignes max
                break
            sample_rows.append(row)
        
        validated_fields = []
        for field in detected_by_pattern:
            field_index = headers.index(field) if field in headers else -1
            if field_index != -1:
                contains_sensitive = False
                for row in sample_rows:
                    if field_index < len(row):
                        cell_value = row[field_index].strip()
                        if is_sensitive_data_enhanced(cell_value, field):
                            contains_sensitive = True
                            break
                
                if contains_sensitive:
                    validated_fields.append(field)
        
        # === ÉTAPE 3: DÉTECTION AUTOMATIQUE POUR CHAMPS MÉDICAUX COURANTS ===
        # Ajouter automatiquement certains champs s'ils contiennent des valeurs typiques
        medical_auto_detect = {
            'diagnostic': ['asthme', 'allergie', 'hypertension', 'diabete', 'malaria', 'paludisme'],
            'groupe_sanguin': ['a+', 'a-', 'b+', 'b-', 'ab+', 'ab-', 'o+', 'o-'],
            'sexe': ['m', 'f', 'h', 'homme', 'femme', 'male', 'female']
        }
        
        for header in headers:
            header_lower = header.lower().strip()
            field_index = headers.index(header)
            
            # Vérifier si le champ correspond à des patterns médicaux connus
            for medical_type, keywords in medical_auto_detect.items():
                if medical_type in header_lower or any(keyword in header_lower for keyword in keywords):
                    # Valider avec le contenu
                    for row in sample_rows:
                        if field_index < len(row):
                            cell_value = row[field_index].strip().lower()
                            if any(keyword in cell_value for keyword in keywords):
                                if header not in validated_fields:
                                    validated_fields.append(header)
                                    print(f"🔍 '{header}' auto-détecté comme champ médical ({medical_type})")
                                break
        
        return list(set(validated_fields))
        
    except Exception as e:
        print(f"Erreur détection IPI améliorée: {e}")
        return []

def is_sensitive_data_enhanced(value, field_name=""):
    """
    Validation améliorée des données sensibles avec contexte du champ
    """
    if not value or len(value.strip()) < 1:
        return False
    
    value = value.strip().lower()
    field_lower = field_name.lower()
    
    # === VALIDATION PAR TYPE DE CHAMP ===
    
    # Diagnostics médicaux
    if 'diagnostic' in field_lower or 'pathologie' in field_lower:
        medical_terms = ['asthme', 'allergie', 'hypertension', 'diabete', 'malaria', 
                        'paludisme', 'tuberculose', 'vih', 'sida', 'cancer']
        return any(term in value for term in medical_terms)
    
    # Groupes sanguins
    if 'sang' in field_lower or 'blood' in field_lower:
        blood_groups = ['a+', 'a-', 'b+', 'b-', 'ab+', 'ab-', 'o+', 'o-']
        return value in blood_groups
    
    # Sexe/Genre
    if 'sexe' in field_lower or 'genre' in field_lower:
        return value in ['m', 'f', 'h', 'homme', 'femme', 'male', 'female']
    
    # === PATTERNS GÉNÉRAUX (existants) ===
    patterns = [
        r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$',  # Email
        r'^(\+221\s?)?\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}$',  # Téléphone
        # Formats de date élargis : 01/01/1990, 1990-01-01, 1-1-90, 1990/1/1, 1 janvier 1990, 1990 janvier 1
        r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})$',
        r'^(\d{4}[/-]\d{1,2}[/-]\d{1,2})$',
        r'^(\d{1,2} [a-zéûîôàèùâêîôûç]+ \d{2,4})$',
        r'^(\d{4} [a-zéûîôàèùâêîôûç]+ \d{1,2})$',
        r'^(\d{1,2} [a-zéûîôàèùâêîôûç]+)$',
        r'^(\d{4})$',  # Année seule (rare mais possible)
    ]
    
    for pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    
    # Noms sénégalais
    SENEGALESE_NAMES = [
        "Awa", "Fatou", "Pape", "Fatoumata", "Modou", "Cheikh", "Amadou", 
        "Aminata", "Mariama", "Ousmane", "Ibrahima", "Abdoulaye"
    ]
    
    if any(name.lower() in value for name in SENEGALESE_NAMES):
        return True
    
    return False

def calculate_enhanced_sensitivity_score(fields):
    """
    Calcul du score de sensibilité avec les poids améliorés
    """
    total_weight = 0
    
    for field in fields:
        field_lower = field.lower()
        
        # Rechercher le poids le plus approprié
        field_weight = 0
        for pattern, weight in ENHANCED_SENSITIVITY_WEIGHTS.items():
            if pattern in field_lower:
                field_weight = max(field_weight, weight)  # Prendre le poids le plus élevé
        
        # Poids par défaut pour champs non reconnus
        if field_weight == 0:
            field_weight = 15
        
        total_weight += field_weight
    
    return min(100, total_weight)

def anonymize_data_enhanced(headers, rows, selected_ipi, methods):
    """Anonymisation améliorée avec de meilleures méthodes"""
    anonymized_rows = []
    colonnes_anonymisees = 0
    
    # Créer un mapping de pseudonymes cohérent
    pseudonym_mapping = {}
    
    for row in rows:
        new_row = []
        for i, cell in enumerate(row):
            header = headers[i] if i < len(headers) else f"champ_{i+1}"
            
            if header in selected_ipi:
                method = methods.get(header, 'none')
                original_value = str(cell).strip()
                
                if method == 'suppression':
                    new_row.append("[SUPPRIMÉ]")
                    colonnes_anonymisees += 1
                
                elif method == 'pseudonymisation':
                    # Pseudonymisation cohérente
                    if original_value not in pseudonym_mapping:
                        pseudonym_mapping[original_value] = f"USER_{secrets.randbelow(99999):05d}"
                    new_row.append(pseudonym_mapping[original_value])
                    colonnes_anonymisees += 1
                
                elif method == 'hachage':
                    # Hachage avec salt
                    salt = "medic_anon_salt_2024"
                    hashed = hashlib.sha256((original_value + salt).encode()).hexdigest()[:16]
                    new_row.append(f"HASH_{hashed}")
                    colonnes_anonymisees += 1
                
                else:
                    new_row.append(cell)
            else:
                new_row.append(cell)
        
        anonymized_rows.append(new_row)
    
    return anonymized_rows, colonnes_anonymisees

# Fonction améliorée pour le calcul du score de sécurité
def calculate_advanced_security_score(fields, methods, file_size=0):
    """Calcul avancé du score de sécurité avec pondération"""
    
    if not fields or not methods:
        return 0
    
    # Pondération par type de données (selon sensibilité RGPD)
    sensitivity_weights = {
        'nom': 35, 'prenom': 30, 'name': 35, 'firstname': 30, 'lastname': 35,
        'date_naissance': 30, 'birth_date': 30, 'ddn': 30, 'age': 20,
        'cni': 40, 'passport': 40, 'passeport': 40, 'carte_identite': 40,
        'adresse': 25, 'address': 25, 'domicile': 25,
        'telephone': 20, 'phone': 20, 'mobile': 20,
        'email': 20, 'mail': 20,
        'patient_id': 25, 'numero_patient': 25,
        'sexe': 15, 'genre': 15, 'gender': 15,
        'profession': 15, 'job': 15, 'travail': 15
    }
    
    # Pondération par méthode d'anonymisation
    method_weights = {
        'suppression': 30,      # Données complètement supprimées
        'hachage': 35,          # Irréversible cryptographiquement
        'pseudonymisation': 25, # Réversible avec clé
        'none': 0               # Aucune protection
    }
    
    total_weighted_score = 0
    max_possible_score = 0
    
    for field in fields:
        # Trouver le poids de sensibilité
        field_lower = field.lower()
        sensitivity = 10  # Valeur par défaut
        
        for pattern, weight in sensitivity_weights.items():
            if pattern in field_lower:
                sensitivity = weight
                break
        
        # Obtenir la méthode utilisée
        method = methods.get(field, 'none')
        method_weight = method_weights.get(method, 0)
        
        # Calculer le score pondéré
        field_score = (sensitivity * method_weight) / 100
        total_weighted_score += field_score
        max_possible_score += sensitivity
    
    if max_possible_score == 0:
        return 0
    
    # Normaliser sur 100 et appliquer des bonus/malus
    base_score = (total_weighted_score / max_possible_score) * 100
    
    # Bonus pour diversité des méthodes
    unique_methods = set(m for m in methods.values() if m != 'none')
    if len(unique_methods) > 1:
        base_score += 5
    
    # Bonus pour méthodes fortes sur données sensibles
    strong_methods_count = sum(1 for m in methods.values() if m in ['hachage', 'suppression'])
    if strong_methods_count > len(fields) * 0.6:
        base_score += 10
    
    # Malus pour trop de pseudonymisation
    pseudo_count = sum(1 for m in methods.values() if m == 'pseudonymisation')
    if pseudo_count > len(fields) * 0.7:
        base_score -= 5
    
    return min(100, max(0, base_score))

def evaluate_gdpr_compliance(fichier, selected_fields, methods):
    """Évalue la conformité RGPD et CDP Sénégal"""
    
    compliance_score = 0
    recommendations = []
    risks = []
    
    # 1. Vérification de la minimisation des données (Article 5(1)(c) RGPD)
    total_fields = len(selected_fields) if selected_fields else 0
    if total_fields <= 5:
        compliance_score += 20
    elif total_fields <= 10:
        compliance_score += 15
        recommendations.append("Considérer la réduction du nombre de champs traités")
    else:
        compliance_score += 10
        risks.append("Trop de champs sélectionnés - Principe de minimisation")
    
    # 2. Évaluation des méthodes d'anonymisation
    method_compliance = {
        'suppression': {'score': 25, 'risk': 'Faible', 'reversible': False},
        'hachage': {'score': 30, 'risk': 'Très faible', 'reversible': False},
        'pseudonymisation': {'score': 20, 'risk': 'Moyen', 'reversible': True},
        'none': {'score': 0, 'risk': 'Élevé', 'reversible': True}
    }
    
    methods_used = list(methods.values()) if methods else []
    method_scores = [method_compliance.get(m, {'score': 0})['score'] for m in methods_used]
    
    if method_scores:
        avg_method_score = sum(method_scores) / len(method_scores)
        compliance_score += min(30, avg_method_score)
    
    # 3. Vérification de la réversibilité (Article 4(5) RGPD)
    reversible_methods = [m for m in methods_used if method_compliance.get(m, {}).get('reversible', True)]
    if not reversible_methods:
        compliance_score += 25
    elif len(reversible_methods) < len(methods_used) / 2:
        compliance_score += 15
        recommendations.append("Privilégier des méthodes non-réversibles pour une meilleure anonymisation")
    else:
        compliance_score += 5
        risks.append("Plusieurs méthodes réversibles utilisées - Risque de ré-identification")
    
    # 4. Évaluation spécifique CDP Sénégal
    sensitive_fields = ['nom', 'prenom', 'cni', 'date_naissance', 'adresse']
    cdp_sensitive_found = [f for f in selected_fields if any(s in f.lower() for s in sensitive_fields)]
    
    if cdp_sensitive_found:
        strong_methods = [f for f in cdp_sensitive_found if methods.get(f) in ['hachage', 'suppression']]
        if len(strong_methods) == len(cdp_sensitive_found):
            compliance_score += 25
        else:
            compliance_score += 10
            recommendations.append("Utiliser hachage ou suppression pour les données d'identité sénégalaises")
    
    # Déterminer le niveau de conformité
    if compliance_score >= 90:
        conformity_level = "Excellente conformité RGPD/CDP"
    elif compliance_score >= 75:
        conformity_level = "Bonne conformité RGPD/CDP"
    elif compliance_score >= 60:
        conformity_level = "Conformité acceptable avec améliorations"
    else:
        conformity_level = "Non-conformité - Révision nécessaire"
    
    return {
        'score': compliance_score,
        'level': conformity_level,
        'recommendations': recommendations,
        'risks': risks,
        'reversible_methods': len(reversible_methods),
        'strong_anonymization': len([m for m in methods_used if m in ['hachage', 'suppression']])
    }

# Ajout dans views.py pour l'utilisation
def create_compliance_report(fichier, selected_ipi, methods, metrics):
    """Crée un rapport de conformité détaillé"""
    
    compliance_eval = evaluate_gdpr_compliance(fichier, selected_ipi, methods)
    
    # Analyser les risques
    risk_analysis = []
    
    # Risque de ré-identification
    if compliance_eval['reversible_methods'] > 0:
        risk_analysis.append(f"Risque de ré-identification: {compliance_eval['reversible_methods']} méthode(s) réversible(s)")
    
    # Risque de perte d'utilité
    if sum(1 for m in methods.values() if m == 'suppression') > len(selected_ipi) * 0.5:
        risk_analysis.append("Risque de perte d'utilité: Trop de suppressions")
    
    # Risque de non-conformité
    if compliance_eval['score'] < 75:
        risk_analysis.append("Risque de non-conformité RGPD/CDP")
    
    # Recommandations spécifiques
    recommendations = compliance_eval['recommendations'].copy()
    
    if metrics['taux_anonymisation'] < 30:
        recommendations.append("Augmenter le taux d'anonymisation (actuellement < 30%)")
    
    if compliance_eval['strong_anonymization'] == 0:
        recommendations.append("Utiliser au moins une méthode forte (hachage/suppression)")
    
    return {
        'conformity_score': compliance_eval['score'],
        'conformity_level': compliance_eval['level'],
        'risk_analysis': '; '.join(risk_analysis) if risk_analysis else "Risques faibles",
        'recommendations': '; '.join(recommendations) if recommendations else "Traitement conforme",
        'gdpr_compliant': compliance_eval['score'] >= 75,
        'cdp_compliant': compliance_eval['score'] >= 70,  # Seuil CDP Sénégal
    }

# Template pour affichage du rapport de conformité
def format_compliance_display(compliance_data):
    """Formate les données de conformité pour affichage"""
    
    score = compliance_data['conformity_score']
    
    if score >= 90:
        badge_color = "green"
        icon = "✅"
    elif score >= 75:
        badge_color = "blue"  
        icon = "✔️"
    elif score >= 60:
        badge_color = "orange"
        icon = "⚠️"
    else:
        badge_color = "red"
        icon = "❌"
    
    return {
        'score': score,
        'badge_color': badge_color,
        'icon': icon,
        'level': compliance_data['conformity_level'],
        'gdpr_status': "Conforme RGPD" if compliance_data['gdpr_compliant'] else "Non-conforme RGPD",
        'cdp_status': "Conforme CDP" if compliance_data['cdp_compliant'] else "Non-conforme CDP"
    }

def register_view(request):
    """
    Vue d'inscription qui s'adapte selon le contexte :
    - Visiteurs : inscription publique avec rôle fixe "Visiteur"
    - Admins connectés : peuvent créer des utilisateurs avec n'importe quel rôle
    """
    
    # Déterminer le contexte
    is_admin_creating = (
        request.user.is_authenticated and 
        request.user.role == 'Administrateur'
    )
    
    # Si un admin est connecté, on est en mode "création d'utilisateur par admin"
    if is_admin_creating:
        page_title = "Créer un utilisateur"
        page_subtitle = "Création d'un nouveau compte utilisateur"
        success_redirect = 'manage_users'  # Rediriger vers la liste des utilisateurs
    else:
        page_title = "Inscription"
        page_subtitle = "Créez votre compte visiteur pour accéder aux données médicales anonymisées"
        success_redirect = 'login'  # Rediriger vers la page de connexion
    
    if request.method == 'POST':
        form = CustomUserCreationForm(
            request.POST, 
            is_admin_creating=is_admin_creating,
            user=request.user if request.user.is_authenticated else None
        )
        
        if form.is_valid():
            user = form.save()
            
            if is_admin_creating:
                # Message pour admin
                messages.success(
                    request, 
                    f"Utilisateur '{user.username}' créé avec succès avec le rôle {user.role}."
                )
                return redirect(success_redirect)
            else:
                # Message pour nouveau visiteur + connexion automatique
                messages.success(
                    request, 
                    f"Compte créé avec succès ! Bienvenue {user.first_name} !"
                )
                login(request, user)  # Connexion automatique pour les nouveaux visiteurs
                return redirect('dashboard')  # ou la page d'accueil
        else:
            # Erreurs de validation
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"{error}")
                    else:
                        field_label = form.fields[field].label if field in form.fields else field
                        messages.error(request, f"{field_label}: {error}")
    else:
        form = CustomUserCreationForm(
            is_admin_creating=is_admin_creating,
            user=request.user if request.user.is_authenticated else None
        )
    
    context = {
        'form': form,
        'is_admin_creating': is_admin_creating,
        'page_title': page_title,
        'page_subtitle': page_subtitle,
    }
    
    return render(request, 'medicanon/register.html', context)

@login_required
def manage_users(request):
    """
    Vue pour lister et gérer les utilisateurs (admins uniquement)
    Les actions de modification/suppression restent ici
    """
    
    # Vérifier que l'utilisateur est admin
    if request.user.role != 'Administrateur':
        raise PermissionDenied("Accès réservé aux administrateurs")
    
    if request.method == 'POST':
        # Mise à jour du rôle d'un utilisateur
        if 'update_role' in request.POST:
            try:
                user_id = request.POST.get('user_id')
                new_role = request.POST.get('new_role')
                
                if not user_id or not new_role:
                    messages.error(request, "Données manquantes pour la mise à jour.")
                    return redirect('manage_users')
                
                user = get_object_or_404(Utilisateur, id=user_id)
                
                # Empêcher un admin de retirer ses propres privilèges
                if user.id == request.user.id and new_role != 'Administrateur':
                    messages.error(request, "Vous ne pouvez pas modifier votre propre rôle d'administrateur.")
                    return redirect('manage_users')
                
                old_role = user.role
                user.role = new_role
                user.save()
                
                messages.success(request, f"Rôle de '{user.username}' modifié de {old_role} vers {new_role}.")
                
            except Utilisateur.DoesNotExist:
                messages.error(request, "Utilisateur introuvable.")
            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour : {str(e)}")
        
        # Suppression d'un utilisateur
        elif 'delete_user' in request.POST:
            try:
                user_id = request.POST.get('user_id')
                
                if not user_id:
                    messages.error(request, "ID utilisateur manquant.")
                    return redirect('manage_users')
                
                user = get_object_or_404(Utilisateur, id=user_id)
                
                # Empêcher l'auto-suppression
                if user.id == request.user.id:
                    messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
                    return redirect('manage_users')
                
                # Empêcher la suppression du dernier admin
                if user.role == 'Administrateur':
                    admin_count = Utilisateur.objects.filter(role='Administrateur').count()
                    if admin_count <= 1:
                        messages.error(request, "Impossible de supprimer le dernier administrateur.")
                        return redirect('manage_users')
                
                username = user.username
                user.delete()
                
                messages.success(request, f"Utilisateur '{username}' supprimé avec succès.")
                
            except Utilisateur.DoesNotExist:
                messages.error(request, "Utilisateur introuvable.")
            except Exception as e:
                messages.error(request, f"Erreur lors de la suppression : {str(e)}")
        
        return redirect('manage_users')
    
    # GET request - afficher la page
    users = Utilisateur.objects.all().order_by('-date_joined')
    
    context = {
        'users': users,
        'total_users': users.count(),
        'admin_count': users.filter(role='Administrateur').count(),
        'agent_count': users.filter(role='Agent').count(),
        'visitor_count': users.filter(role='Visiteur').count(),
    }
    
    return render(request, 'medicanon/manage_users.html', context)

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

def calculate_sensitivity_score(fields):
    sensitivity_weights = {'nom': 30, 'prenom': 25, 'adresse': 20, 'date_naissance': 15, 'email': 10, 'patient': 20}
    total_weight = sum(sensitivity_weights.get(field.lower(), 0) for field in fields)
    return min(100, total_weight)

def anonymize_with_complete_preservation(headers, original_rows, selected_ipi, methods):
    """
    Anonymise les champs sélectionnés et PRÉSERVE tous les autres champs intacts
    """
    print(f"=== DÉBUT ANONYMISATION ===")
    print(f"Headers reçus: {headers}")
    print(f"Nombre de lignes à traiter: {len(original_rows)}")
    print(f"Champs à anonymiser: {selected_ipi}")
    print(f"Méthodes: {methods}")
    
    processed_rows = []
    anonymized_fields = []
    preserved_fields = []
    
    # Identifier les champs préservés vs anonymisés
    for header in headers:
        if header in selected_ipi:
            anonymized_fields.append(header)
        else:
            preserved_fields.append(header)
    
    print(f"Champs qui seront anonymisés: {anonymized_fields}")
    print(f"Champs qui seront préservés: {preserved_fields}")
    
    # Créer un mapping de pseudonymes cohérent
    pseudonym_mapping = {}
    
    # Traiter chaque ligne
    for row_index, row in enumerate(original_rows):
        new_row = []
        
        for i, cell in enumerate(row):
            header = headers[i] if i < len(headers) else f"champ_{i+1}"
            
            if header in selected_ipi:
                # === CHAMP À ANONYMISER ===
                method = methods.get(header, 'none')
                original_value = str(cell).strip()
                
                if method == 'suppression':
                    new_row.append("[SUPPRIMÉ]")
                
                elif method == 'pseudonymisation':
                    # Pseudonymisation cohérente
                    if original_value not in pseudonym_mapping:
                        pseudonym_mapping[original_value] = f"USER_{secrets.randbelow(99999):05d}"
                    new_row.append(pseudonym_mapping[original_value])
                
                elif method == 'hachage':
                    # Hachage avec salt
                    salt = "medic_anon_salt_2024"
                    hashed = hashlib.sha256((original_value + salt).encode()).hexdigest()[:16]
                    new_row.append(f"HASH_{hashed}")
                
                else:
                    # Si 'none', préserver la valeur originale
                    new_row.append(cell)
            
            else:
                # === CHAMP PRÉSERVÉ INTACT ===
                new_row.append(cell)  # Garder la valeur originale
        
        processed_rows.append(new_row)
        
        # Debug pour les premières lignes
        if row_index < 2:
            print(f"Ligne {row_index + 1} originale: {row}")
            print(f"Ligne {row_index + 1} traitée: {new_row}")
    
    result_info = {
        'anonymized_fields': anonymized_fields,
        'preserved_fields': preserved_fields,
        'methods_used': methods,
        'total_anonymized_columns': len(anonymized_fields),
        'total_preserved_columns': len(preserved_fields)
    }
    
    print(f"=== RÉSULTAT ANONYMISATION ===")
    print(f"Lignes traitées: {len(processed_rows)}")
    print(f"Colonnes anonymisées: {len(anonymized_fields)}")
    print(f"Colonnes préservées: {len(preserved_fields)}")
    
    return processed_rows, result_info

@login_required
def download_from_binary(request, fichier_id):
    """
    NOUVELLE VUE : Télécharge les données depuis le stockage binaire
    """
    try:
        fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
        
        if fichier.statut != 'Anonymisé' or not fichier.donnees_completes_binaire:
            messages.error(request, "Aucune donnée anonymisée disponible.")
            return redirect('anonymize')
        
        # Récupérer toutes les données
        all_data = fichier.get_toutes_les_donnees()
        
        if not all_data:
            messages.error(request, "Erreur lors de la décompression des données.")
            return redirect('anonymize')
        
        # Générer le CSV complet
        output = io.StringIO()
        writer = csv.writer(output)
        
        # En-têtes
        writer.writerow(all_data['headers'])
        
        # Toutes les données
        for row in all_data['rows']:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        
        # Réponse HTTP
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="anonymized_complete_{fichier.nom_fichier}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f"Erreur téléchargement: {str(e)}")
        return redirect('anonymize')

@login_required
def anonymize(request):
    """
    Vue principale pour le processus d'anonymisation en 5 étapes.
    Cette version est corrigée pour un flux de travail logique et une sauvegarde robuste.
    """
    # --- Initialisation des variables ---
    step = int(request.GET.get('step', 1))
    fichier_id = request.GET.get('fichier_id')
    fichiers = Fichier.objects.filter(utilisateur=request.user).order_by('-date_import')
    
    # Variables pour le contexte du template
    context_data = {
        'uploaded_file': request.session.get('uploaded_file'),
        'ipi_fields': [],
        'sensitivity_score': 0,
        'headers': [],
        'original': [],
        'anonymized': [],
        'lignes_traitees': 0,
        'colonnes_anonymisees': 0,
        'taux_anonymisation': 0,
        'score_securite': 0,
    }

    # --- ÉTAPE 1 & 2 : Récupération des infos du fichier si un ID est présent ---
    if fichier_id:
        try:
            fichier_instance = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
            context_data['uploaded_file'] = {
                'nom_fichier': fichier_instance.nom_fichier,
                'extension': fichier_instance.nom_fichier.split('.')[-1].lower(),
                'id': fichier_id
            }
            request.session['uploaded_file'] = context_data['uploaded_file']
            
            if step == 2:
                context_data['ipi_fields'] = detect_ipi_fields_csv_only(fichier_instance)
                context_data['sensitivity_score'] = calculate_enhanced_sensitivity_score(context_data['ipi_fields'])

        except Fichier.DoesNotExist:
            messages.error(request, "Fichier introuvable.")
            if 'uploaded_file' in request.session:
                del request.session['uploaded_file']
            return redirect('anonymize')

    # --- Nettoyage si retour à l'étape 1 ou demande de changement de fichier ---
    if step == 1:
        # Supprimer le fichier importé non anonymisé si présent
        uploaded_file = request.session.get('uploaded_file')
        if uploaded_file and uploaded_file.get('id'):
            try:
                fichier_to_delete = Fichier.objects.filter(id=uploaded_file['id'], utilisateur=request.user, statut='Importé').first()
                if fichier_to_delete:
                    if fichier_to_delete.fichier:
                        fichier_to_delete.fichier.delete(save=False)
                    fichier_to_delete.delete()
            except Exception as e:
                print(f"Erreur suppression fichier non anonymisé: {e}")
        # Nettoyer la session
        for key in list(request.session.keys()):
            if key.startswith(('uploaded_file', 'selected_ipi', 'methods', 'headers', 'original', 'anonymized')):
                del request.session[key]

    # --- Gestion des requêtes POST pour chaque étape ---
    if request.method == 'POST':
        
        # === ÉTAPE 1 : Import du fichier ===
        if 'fichier' in request.FILES:
            uploaded_file_obj = request.FILES['fichier']
            if not uploaded_file_obj.name.lower().endswith('.csv'):
                messages.error(request, "Seuls les fichiers CSV sont acceptés.")
                return redirect('anonymize')
            
            try:
                fichier_instance = Fichier.objects.create(
                    fichier=uploaded_file_obj,
                    nom_fichier=uploaded_file_obj.name,
                    statut='Importé',
                    utilisateur=request.user,
                    taille_originale=uploaded_file_obj.size # On stocke la taille dès l'import
                )
                request.session['uploaded_file'] = {
                    'nom_fichier': fichier_instance.nom_fichier, 
                    'extension': fichier_instance.nom_fichier.split('.')[-1].lower(), 
                    'id': str(fichier_instance.id)
                }
                messages.success(request, "Fichier importé avec succès.")
                return redirect(reverse('anonymize') + f'?step=2&fichier_id={fichier_instance.id}')
            except Exception as e:
                messages.error(request, f"Erreur lors de l'import : {str(e)}")
                return redirect('anonymize')

        # === ÉTAPE 2 : Configuration de l'anonymisation ===
        elif 'from_config' in request.POST:
            fichier_id = request.POST.get('fichier_id')
            if not fichier_id:
                messages.error(request, "Aucun fichier sélectionné.")
                return redirect(reverse('anonymize') + '?step=2')

            selected_ipi = request.POST.getlist('ipi_fields')
            if not selected_ipi:
                messages.error(request, "Veuillez sélectionner au moins un champ à anonymiser.")
                return redirect(reverse('anonymize') + f'?step=2&fichier_id={fichier_id}')

            # CORRECTION : Utilisation de slugify pour récupérer les méthodes
            methods = {field: request.POST.get(f'method_{slugify(field)}', 'none') for field in selected_ipi}
            
            if all(method == 'none' for method in methods.values()):
                messages.warning(request, "Aucune méthode d'anonymisation n'a été choisie. Les données ne seront pas modifiées.")

            request.session['selected_ipi'] = selected_ipi
            request.session['methods'] = methods
            
            try:
                fichier_instance = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
                fichier_instance.fichier.seek(0)
                decoded_file = fichier_instance.fichier.read().decode('utf-8', errors='ignore')
                csv_reader = csv.reader(io.StringIO(decoded_file))
                headers = next(csv_reader, [])
                original_rows = list(csv_reader)

                if not headers or not original_rows:
                    messages.error(request, "Le fichier CSV semble vide ou mal formaté.")
                    return redirect(reverse('anonymize') + f'?step=2&fichier_id={fichier_id}')

                anonymized_rows, info = anonymize_with_complete_preservation(headers, original_rows, selected_ipi, methods)
                
                # Stockage des données traitées en session pour les étapes suivantes
                request.session.update({
                    'headers': headers,
                    'original': original_rows,
                    'anonymized': anonymized_rows,
                    'lignes_traitees': len(original_rows),
                    'colonnes_anonymisees': info['total_anonymized_columns'],
                    'taux_anonymisation': (info['total_anonymized_columns'] / len(headers)) * 100 if headers else 0,
                    'score_securite': calculate_advanced_security_score(selected_ipi, methods),
                })
                
                messages.success(request, "Configuration appliquée. Veuillez vérifier l'aperçu.")
                return redirect(reverse('anonymize') + f'?step=3&fichier_id={fichier_id}')

            except Exception as e:
                messages.error(request, f"Erreur lors du traitement du fichier : {str(e)}")
                return redirect(reverse('anonymize') + f'?step=2&fichier_id={fichier_id}')

        # === ÉTAPE 3 : Clic sur "Lancer l'Anonymisation" -> Redirection vers l'étape 4 ===
        elif 'from_anonymize' in request.POST:
            fichier_id = request.POST.get('fichier_id')
            if not fichier_id:
                messages.error(request, "ID de fichier manquant. Veuillez recommencer.")
                return redirect('anonymize')
            
            messages.info(request, "Traitement terminé ! Voici les résultats et les options d'export.")
            return redirect(reverse('anonymize') + f'?step=4&fichier_id={fichier_id}')

        # === ÉTAPE 4 : Clic sur "Exporter & Sauvegarder" -> Sauvegarde finale ===
        elif 'from_export' in request.POST:
            fichier_id = request.POST.get('fichier_id')
            if not fichier_id:
                messages.error(request, "Aucun fichier sélectionné pour la sauvegarde.")
                return redirect('anonymize')

            try:
                # Récupérer toutes les données nécessaires depuis la session
                session_data = {
                    'selected_ipi': request.session.get('selected_ipi', []),
                    'methods': request.session.get('methods', {}),
                    'headers': request.session.get('headers', []),
                    'original': request.session.get('original', []),
                    'anonymized': request.session.get('anonymized', [])
                }
                if not all(session_data.values()):
                    messages.error(request, "Votre session a expiré. Veuillez recommencer le processus.")
                    return redirect('anonymize')

                fichier_instance = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
                
                # 1. Stocker les données anonymisées binaires dans le modèle Fichier
                anonymization_info = {
                    'anonymized_fields': session_data['selected_ipi'],
                    'preserved_fields': [h for h in session_data['headers'] if h not in session_data['selected_ipi']],
                    'methods_used': session_data['methods']
                }
                fichier_instance.store_donnees_completes(
                    session_data['headers'], session_data['anonymized'], anonymization_info
                )

                # 2. Supprimer le fichier physique original après anonymisation
                if fichier_instance.fichier:
                    fichier_instance.fichier.delete(save=False)
                    fichier_instance.fichier = None

                # 3. Mettre à jour les métriques du fichier
                fichier_instance.nombre_lignes = len(session_data['original'])
                fichier_instance.nombre_colonnes = len(session_data['headers'])
                fichier_instance.partage = request.POST.get('share_hub') == '1'
                fichier_instance.save()

                # 4. Créer l'historique et les rapports associés
                historique = Historique.objects.create(
                    fichier=fichier_instance,
                    utilisateur=request.user,
                    partage=fichier_instance.partage,
                    méthode_anonymisation=", ".join([f"{f}: {m}" for f, m in session_data['methods'].items()]),
                    statut='Terminé'
                )
                Métriques.objects.create(
                    historique=historique,
                    lignes_traitees=fichier_instance.nombre_lignes,
                    colonnes_anonymisees=len(session_data['selected_ipi']),
                    taux_anonymisation=(len(session_data['selected_ipi']) / fichier_instance.nombre_colonnes) * 100,
                    score_securite=calculate_advanced_security_score(session_data['selected_ipi'], session_data['methods'])
                )
                RapportConformité.objects.create(
                    historique=historique,
                    analyse_risques="Analyse des risques effectuée.",
                    recommandations="Traitement conforme aux standards.",
                    conformite="Conforme RGPD/CDP"
                )

                # 5. Nettoyer la session
                for key in list(request.session.keys()):
                    if key.startswith(('uploaded_file', 'selected_ipi', 'methods', 'headers', 'original', 'anonymized')):
                        del request.session[key]
                
                messages.success(request, f"Fichier '{fichier_instance.nom_fichier}' anonymisé et sauvegardé avec succès !")
                return redirect(reverse('anonymize') + f'?step=5')

            except Exception as e:
                messages.error(request, f"Erreur critique lors de la sauvegarde finale : {str(e)}")
                return redirect('anonymize')

    # --- Préparation du contexte pour le rendu du template ---
    if step >= 3:
        context_data.update({
            'headers': request.session.get('headers', []),
            'original': request.session.get('original', []),
            'anonymized': request.session.get('anonymized', []),
            'lignes_traitees': request.session.get('lignes_traitees', 0),
            'colonnes_anonymisees': request.session.get('colonnes_anonymisees', 0),
            'taux_anonymisation': request.session.get('taux_anonymisation', 0),
            'score_securite': request.session.get('score_securite', 0),
        })

    final_context = {
        'step': step,
        'fichiers': fichiers,
        'methodes': ['Suppression', 'Pseudonymisation', 'Hachage'],
        'fichier_id': fichier_id,
        'anonymized_count': fichiers.filter(statut='Anonymisé').count() if fichiers else 0,
        **context_data
    }
    
    return render(request, 'medicanon/anonymize.html', final_context)

def download_public_file(request, fichier_id ):
    """
    Permet à n'importe qui de télécharger un fichier anonymisé et partagé.
    Lit les données directement depuis la base de données.
    """
    try:
        # Récupérer le fichier. On ne filtre pas par utilisateur car c'est public.
        fichier = get_object_or_404(Fichier, id=fichier_id)

        # Vérifier les conditions de sécurité
        if fichier.statut != 'Anonymisé' or not fichier.partage:
            messages.error(request, "Ce fichier n'est pas disponible au téléchargement public.")
            # Rediriger vers le hub ou une autre page appropriée
            return redirect('public_hub') 

        # Récupérer les données depuis le champ binaire
        all_data = fichier.get_toutes_les_donnees()

        if not all_data or 'headers' not in all_data or 'rows' not in all_data:
            messages.error(request, "Les données anonymisées pour ce fichier sont corrompues ou introuvables.")
            return redirect('public_hub')

        # Générer le contenu du fichier CSV en mémoire
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Écrire les en-têtes
        writer.writerow(all_data['headers'])
        
        # Écrire les lignes de données
        writer.writerows(all_data['rows'])
        
        csv_content = output.getvalue()
        
        # Créer la réponse HTTP pour le téléchargement
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="anonymized_{fichier.nom_fichier}"'
        
        return response

    except Http404:
        messages.error(request, "Le fichier demandé n'existe pas.")
        return redirect('public_hub')
    except Exception as e:
        messages.error(request, f"Une erreur est survenue lors de la préparation du téléchargement : {str(e)}")
        return redirect('public_hub')



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
def download_hybrid(request, fichier_id):
    """
    Téléchargement hybride : depuis la base si exporté, sinon depuis la session
    """
    try:
        fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
        
        # Vérifier si le fichier est déjà exporté/sauvegardé
        if fichier.statut == 'Anonymisé' and fichier.donnees_completes_binaire:
            # Fichier déjà exporté -> utiliser la vue publique
            return download_public_file(request, fichier_id)
        else:
            # Fichier pas encore exporté -> télécharger depuis la session
            session_data = {
                'headers': request.session.get('headers', []),
                'original': request.session.get('original', []),
                'anonymized': request.session.get('anonymized', [])
            }
            
            if not all(session_data.values()):
                messages.error(request, "Aucune donnée anonymisée disponible en session. Veuillez d'abord exporter le fichier.")
                return redirect('anonymize')
            
            # Générer le CSV depuis la session
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Écrire les en-têtes
            writer.writerow(session_data['headers'])
            
            # Écrire les lignes de données anonymisées
            writer.writerows(session_data['anonymized'])
            
            csv_content = output.getvalue()
            
            # Créer la réponse HTTP pour le téléchargement
            response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="anonymized_{fichier.nom_fichier}"'
            
            messages.info(request, "Téléchargement depuis les données en session. Pour un accès permanent, exportez d'abord le fichier.")
            return response
            
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement : {str(e)}")
        return redirect('anonymize')

@login_required
def metrics(request):
    if request.user.is_superuser or request.user.is_staff:
        metriques = Métriques.objects.all()
    else:
        historiques = Historique.objects.filter(utilisateur=request.user)
        metriques = Métriques.objects.filter(historique__in=historiques)
    return render(request, 'medicanon/metrics.html', {'metriques': metriques})

@login_required
def compliance_report(request):
    if request.user.is_superuser or request.user.is_staff:
        rapports = RapportConformité.objects.all()
    else:
        historiques = Historique.objects.filter(utilisateur=request.user)
        rapports = RapportConformité.objects.filter(historique__in=historiques)
    return render(request, 'medicanon/compliance_report.html', {'rapports': rapports})


def custom_logout(request):
    logout(request)
    return redirect('accueil')

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

@require_GET
def file_preview_api(request, fichier_id):
    """API pour récupérer l'aperçu d'un fichier anonymisé"""
    
    try:
        fichier = get_object_or_404(Fichier, id=fichier_id)
        
        # Vérifier que le fichier est anonymisé et partagé publiquement
        if fichier.statut != 'Anonymisé' or not fichier.partage:
            return JsonResponse({
                'error': 'Fichier non disponible pour aperçu',
                'message': 'Ce fichier n\'est pas anonymisé ou n\'est pas partagé publiquement.'
            }, status=403)
        
        # Logger l'accès pour audit
        if request.user.is_authenticated:
            AuditLog.objects.create(
                utilisateur=request.user,
                action='VIEW',
                fichier=fichier,
                details={'action': 'preview_access', 'ip': get_client_ip(request)},
                ip_address=get_client_ip(request)
            )
        
        # Déterminer le type de fichier
        file_extension = fichier.nom_fichier.split('.')[-1].lower()
        
        # Préparer les métadonnées de base
        metadata = {
            'id': fichier.id,
            'name': fichier.nom_fichier,
            'type': file_extension,
            'size': get_file_size_display(fichier),
            'date': fichier.date_import.strftime('%d/%m/%Y'),
            'status': fichier.statut,
            'score': calculate_display_score(fichier)
        }
        
        # Générer l'aperçu selon le type
        if file_extension == 'csv':
            preview_data = generate_csv_preview(fichier)
        else:
            preview_data = {'type': 'unsupported', 'message': 'Type de fichier non supporté pour l\'aperçu'}
        
        return JsonResponse({
            'success': True,
            'metadata': metadata,
            'preview': preview_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': 'Erreur lors de la génération de l\'aperçu',
            'message': str(e)
        }, status=500)

def generate_csv_preview(fichier):
    """Génère un aperçu pour les fichiers CSV"""
    try:
        # Utiliser le fichier anonymisé si disponible, sinon le fichier original
        file_to_read = fichier.fichier_anonymise if fichier.fichier_anonymise else fichier.fichier
        
        file_to_read.seek(0)
        content = file_to_read.read().decode('utf-8', errors='ignore')
        file_to_read.seek(0)
        
        # Parser le CSV
        csv_reader = csv.reader(io.StringIO(content))
        
        # Lire les en-têtes
        headers = next(csv_reader, [])
        
        # Lire les 5 premières lignes de données
        rows = []
        for i, row in enumerate(csv_reader):
            if i >= 5:  # Limiter à 5 lignes pour l'aperçu
                break
            rows.append(row)
        
        # Statistiques
        file_to_read.seek(0)
        total_lines = sum(1 for line in io.StringIO(content)) - 1  # -1 pour les en-têtes
        
        return {
            'type': 'csv',
            'headers': headers,
            'rows': rows,
            'total_rows': total_lines,
            'total_columns': len(headers),
            'preview_rows': len(rows)
        }
        
    except Exception as e:
        return {
            'type': 'error',
            'message': f'Erreur lors de la lecture du CSV: {str(e)}'
        }

def get_file_size_display(fichier):
    """Retourne la taille du fichier en format lisible"""
    try:
        file_to_check = fichier.fichier_anonymise if fichier.fichier_anonymise else fichier.fichier
        size_bytes = file_to_check.size
        
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.1f} MB"
        else:
            return f"{size_bytes/(1024**3):.1f} GB"
    except:
        return "Taille inconnue"

def calculate_display_score(fichier):
    """Calcule un score d'affichage pour le fichier"""
    try:
        # Récupérer les métriques du fichier
        from .models import Métriques, Historique
        
        historique = Historique.objects.filter(fichier=fichier).first()
        if historique:
            metriques = Métriques.objects.filter(historique=historique).first()
            if metriques:
                return f"{metriques.score_securite:.0f}/100"
        
        # Score par défaut basé sur le statut
        if fichier.statut == 'Anonymisé':
            return "95/100"
        else:
            return "0/100"
    except:
        return "95/100"

def get_client_ip(request):
    """Obtient l'IP réelle du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
def preview_file(request, fichier_id):
    """
    Aperçu du contenu d'un fichier anonymisé (pour l'interface)
    """
    try:
        fichier = get_object_or_404(Fichier, id=fichier_id, utilisateur=request.user)
        
        print(f"DEBUG: Fichier trouvé - ID: {fichier.id}, Statut: {fichier.statut}, Nom: {fichier.nom_fichier}")
        
        if fichier.statut != 'Anonymisé':
            return JsonResponse({
                'success': False,
                'error': f'Le fichier doit être anonymisé pour être prévisualisé (statut actuel: {fichier.statut})'
            })
        
        # Récupérer les données du fichier
        headers = []
        rows = []
        anonymization_info = {}
        
        print(f"DEBUG: Vérification des données binaires - Présentes: {bool(fichier.donnees_completes_binaire)}")
        
        if fichier.donnees_completes_binaire:
            # Fichier exporté - lire depuis la base
            import pickle
            import gzip
            import io
            
            try:
                # Essayer de lire comme pickle normal
                data = pickle.loads(fichier.donnees_completes_binaire)
                print("DEBUG: Données lues avec pickle normal")
            except Exception as e1:
                print(f"DEBUG: Erreur pickle normal: {e1}")
                try:
                    # Essayer de lire comme pickle compressé avec gzip
                    with gzip.open(io.BytesIO(fichier.donnees_completes_binaire), 'rb') as f:
                        data = pickle.load(f)
                    print("DEBUG: Données lues avec pickle + gzip")
                except Exception as e2:
                    print(f"DEBUG: Erreur pickle + gzip: {e2}")
                    try:
                        # Essayer de décompresser d'abord puis pickle
                        decompressed = gzip.decompress(fichier.donnees_completes_binaire)
                        data = pickle.loads(decompressed)
                        print("DEBUG: Données lues avec décompression + pickle")
                    except Exception as e3:
                        print(f"DEBUG: Erreur décompression + pickle: {e3}")
                        # Si rien ne marche, essayer de lire comme JSON ou autre format
                        try:
                            import json
                            # Essayer de décoder comme JSON
                            data_str = fichier.donnees_completes_binaire.decode('utf-8')
                            data = json.loads(data_str)
                            print("DEBUG: Données lues avec JSON")
                        except Exception as e4:
                            print(f"DEBUG: Erreur JSON: {e4}")
                            return JsonResponse({
                                'success': False,
                                'error': f'Format de données non reconnu. Erreurs: pickle={e1}, gzip={e2}, decompress={e3}, json={e4}'
                            })
                
            headers = data.get('headers', [])
            rows = data.get('rows', [])  # Changé de 'anonymized' à 'rows'
            anonymization_info = data.get('anonymization_info', {})
            
            print(f"DEBUG: Données extraites - Headers: {len(headers)}, Rows: {len(rows)}")
            print(f"DEBUG: Clés disponibles dans data: {list(data.keys())}")
            print(f"DEBUG: Structure des données: {type(data)}")
            
            # Si rows est vide, essayer d'autres clés possibles
            if not rows:
                rows = data.get('anonymized', [])
                print(f"DEBUG: Essai avec 'anonymized': {len(rows)} lignes")
            if not rows:
                rows = data.get('processed_rows', [])
                print(f"DEBUG: Essai avec 'processed_rows': {len(rows)} lignes")
            if not rows:
                rows = data.get('data', [])
                print(f"DEBUG: Essai avec 'data': {len(rows)} lignes")
            
        else:
            # Fichier en session - lire depuis la session
            session_data = request.session.get('anonymization_data', {})
            print(f"DEBUG: Données de session - Présentes: {bool(session_data)}")
            
            if not session_data:
                return JsonResponse({
                    'success': False,
                    'error': 'Aucune donnée trouvée dans la base de données ni dans la session. Le fichier n\'a peut-être pas été exporté.'
                })
            
            headers = session_data.get('headers', [])
            rows = session_data.get('rows', [])  # Changé de 'anonymized' à 'rows'
            anonymization_info = session_data.get('anonymization_info', {})
            
            print(f"DEBUG: Données de session extraites - Headers: {len(headers)}, Rows: {len(rows)}")
            print(f"DEBUG: Clés disponibles dans session_data: {list(session_data.keys())}")
            
            # Si rows est vide, essayer d'autres clés possibles
            if not rows:
                rows = session_data.get('anonymized', [])
                print(f"DEBUG: Session - Essai avec 'anonymized': {len(rows)} lignes")
            if not rows:
                rows = session_data.get('processed_rows', [])
                print(f"DEBUG: Session - Essai avec 'processed_rows': {len(rows)} lignes")
            if not rows:
                rows = session_data.get('data', [])
                print(f"DEBUG: Session - Essai avec 'data': {len(rows)} lignes")
        
        # Vérifier que nous avons des données
        if not headers or not rows:
            return JsonResponse({
                'success': False,
                'error': f'Aucune donnée à afficher. Headers: {len(headers)}, Rows: {len(rows)}'
            })
        
        # Créer l'aperçu HTML
        preview_html = '<div class="space-y-4">'
        
        # Informations sur l'anonymisation
        if anonymization_info:
            preview_html += '<div class="bg-blue-50 p-3 rounded border">'
            preview_html += '<h4 class="font-medium text-blue-900 mb-2">📊 Informations d\'anonymisation</h4>'
            preview_html += '<div class="text-sm text-blue-800">'
            
            anonymized_fields = anonymization_info.get("anonymized_fields", [])
            preserved_fields = anonymization_info.get("preserved_fields", [])
            method = anonymization_info.get("method", "Non spécifiée")
            
            preview_html += f'<p><strong>Champs anonymisés:</strong> {len(anonymized_fields)}</p>'
            preview_html += f'<p><strong>Champs préservés:</strong> {len(preserved_fields)}</p>'
            preview_html += f'<p><strong>Méthode:</strong> {method}</p>'
            
            if anonymized_fields:
                preview_html += f'<p><strong>Champs anonymisés:</strong> {", ".join(anonymized_fields[:5])}'
                if len(anonymized_fields) > 5:
                    preview_html += f'... (+{len(anonymized_fields) - 5} autres)'
                preview_html += '</p>'
            
            preview_html += '</div></div>'
        
        # Tableau des données
        preview_html += '<div class="overflow-x-auto">'
        preview_html += '<table class="min-w-full border border-gray-300">'
        
        # En-têtes
        preview_html += '<thead><tr class="bg-gray-100">'
        for header in headers:
            # Échapper les caractères spéciaux pour éviter les problèmes HTML
            safe_header = str(header).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            preview_html += f'<th class="border border-gray-300 px-3 py-2 text-left text-sm font-medium">{safe_header}</th>'
        preview_html += '</tr></thead>'
        
        # Lignes (limitées à 10 pour l'aperçu)
        preview_html += '<tbody>'
        for i, row in enumerate(rows[:10]):
            row_class = 'bg-white' if i % 2 == 0 else 'bg-gray-50'
            preview_html += f'<tr class="{row_class}">'
            for cell in row:
                # Échapper les caractères spéciaux
                safe_cell = str(cell).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                preview_html += f'<td class="border border-gray-300 px-3 py-2 text-sm">{safe_cell}</td>'
            preview_html += '</tr>'
        preview_html += '</tbody>'
        preview_html += '</table>'
        
        if len(rows) > 10:
            preview_html += f'<p class="text-sm text-gray-600 mt-2">Aperçu des 10 premières lignes sur {len(rows)} lignes totales</p>'
        
        preview_html += '</div>'
        preview_html += '</div>'
        
        return JsonResponse({
            'success': True,
            'content': preview_html
        })
        
    except Exception as e:
        import traceback
        print(f"Erreur dans preview_file: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Erreur serveur: {str(e)}'
        })

@login_required
def historique_view(request):
    """
    Vue dédiée pour afficher l'historique des fichiers anonymisés
    """
    # Récupérer tous les fichiers de l'utilisateur
    fichiers = Fichier.objects.filter(utilisateur=request.user).order_by('-date_import')
    
    # Calculer les statistiques
    total_fichiers = fichiers.count()
    fichiers_anonymises = fichiers.filter(statut='Anonymisé').count()
    fichiers_importes = fichiers.filter(statut='Importé').count()
    
    context = {
        'fichiers': fichiers,
        'total_fichiers': total_fichiers,
        'fichiers_anonymises': fichiers_anonymises,
        'fichiers_importes': fichiers_importes,
        'show_historique_only': True,  # Flag pour indiquer qu'on affiche seulement l'historique
    }
    
    return render(request, 'medicanon/historique.html', context)

@login_required
def test_preview(request):
    """
    Vue de test pour vérifier que l'URL preview_file fonctionne
    """
    return JsonResponse({
        'success': True,
        'message': 'Test preview fonctionne correctement'
    })

