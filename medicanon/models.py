from django.contrib.auth.models import AbstractUser
from django.db import models
import pickle
import gzip
from django.utils import timezone 

class Utilisateur(AbstractUser):
    role = models.CharField(max_length=20, choices=[
        ('Administrateur', 'Administrateur'),
        ('Agent', 'Agent'),
        ('Visiteur', 'Visiteur'),
    ], default='Visiteur')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Fichier(models.Model):
    nom_fichier = models.CharField(max_length=255)
    fichier = models.FileField(upload_to='fichiers/', null=True, blank=True)  # Optionnel maintenant
    
    # === NOUVEAUX CHAMPS POUR STOCKAGE BINAIRE ===
    donnees_completes_binaire = models.BinaryField(
        null=True, 
        blank=True,
        help_text="TOUTES les données (anonymisées + préservées) en format binaire"
    )
    
    # Métadonnées de l'anonymisation
    champs_anonymises = models.TextField(blank=True, help_text="Liste des champs anonymisés")
    champs_preserves = models.TextField(blank=True, help_text="Liste des champs préservés")
    methodes_anonymisation = models.JSONField(default=dict, help_text="Détail des méthodes par champ")
    
    # Statistiques
    nombre_lignes = models.IntegerField(default=0)
    nombre_colonnes = models.IntegerField(default=0)
    taille_originale = models.BigIntegerField(default=0)
    
    date_import = models.DateTimeField(auto_now_add=True)
    date_anonymisation = models.DateTimeField(null=True, blank=True)  # NOUVEAU
    
    statut = models.CharField(max_length=20, choices=[
        ('Importé', 'Importé'),
        ('En cours', 'En cours'),
        ('Anonymisé', 'Anonymisé'),
        ('Exporté', 'Exporté'),
    ], default='Importé')
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True)
    partage = models.BooleanField(default=False)

    def __str__(self):
        return self.nom_fichier
    
    # === NOUVELLES MÉTHODES ===
   
    def get_toutes_les_donnees(self):
        """Récupère TOUTES les données depuis le format binaire"""
        if not hasattr(self, 'donnees_completes_binaire') or not self.donnees_completes_binaire:
            print("Pas de données binaires trouvées")
            return None
        
        try:
            print(f"Décompression des données binaires... Taille: {len(self.donnees_completes_binaire)} bytes")
            compressed_data = self.donnees_completes_binaire
            decompressed_data = gzip.decompress(compressed_data)
            data_dict = pickle.loads(decompressed_data)
            
            print(f"Données décompressées avec succès!")
            print(f"Headers: {data_dict.get('headers', [])}")
            print(f"Nombre de lignes: {len(data_dict.get('rows', []))}")
            
            return {
                'headers': data_dict.get('headers', []),
                'rows': data_dict.get('rows', []),
                'anonymized_fields': data_dict.get('anonymized_fields', []),
                'preserved_fields': data_dict.get('preserved_fields', []),
                'metadata': data_dict.get('metadata', {})
            }
        except Exception as e:
            print(f"Erreur décompression: {e}")
            return None
        
    def store_donnees_completes(self, headers, processed_rows, anonymization_info):
        """Stocke TOUTES les données en format binaire"""
        try:
            print(f"=== DÉBUT STOCKAGE BINAIRE ===")
            print(f"Headers à stocker: {headers}")
            print(f"Nombre de lignes à stocker: {len(processed_rows)}")
            print(f"Info anonymisation: {anonymization_info}")
            
            complete_data = {
                'headers': headers,
                'rows': processed_rows,
                'anonymized_fields': anonymization_info.get('anonymized_fields', []),
                'preserved_fields': anonymization_info.get('preserved_fields', []),
                'methods_used': anonymization_info.get('methods_used', {}),
                'metadata': {
                    'total_rows': len(processed_rows),
                    'total_columns': len(headers),
                    'anonymization_date': timezone.now().isoformat(),
                    'version': '2.0'
                }
            }
            
            print(f"Données à compresser préparées: {len(str(complete_data))} caractères")
            
            # Sérialiser avec pickle
            serialized_data = pickle.dumps(complete_data, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"Données sérialisées: {len(serialized_data)} bytes")
            
            # Compresser avec gzip
            compressed_data = gzip.compress(serialized_data, compresslevel=9)
            print(f"Données compressées: {len(compressed_data)} bytes")
            
            # Stocker
            if hasattr(self, 'donnees_completes_binaire'):
                self.donnees_completes_binaire = compressed_data
                
                # Vérifier si les champs existent avant de les assigner
                if hasattr(self, 'champs_anonymises'):
                    self.champs_anonymises = ', '.join(anonymization_info.get('anonymized_fields', []))
                if hasattr(self, 'champs_preserves'):
                    self.champs_preserves = ', '.join(anonymization_info.get('preserved_fields', []))
                if hasattr(self, 'methodes_anonymisation'):
                    self.methodes_anonymisation = anonymization_info.get('methods_used', {})
                if hasattr(self, 'date_anonymisation'):
                    self.date_anonymisation = timezone.now()
                
                self.statut = 'Anonymisé'
                self.save()
                
                print(f"Stockage réussi ! Fichier mis à jour avec statut: {self.statut}")
                return True
            else:
                print("ERREUR: Le champ donnees_completes_binaire n'existe pas sur ce modèle")
                print("Vous devez d'abord créer et exécuter les migrations!")
                return False
                
        except Exception as e:
            print(f"Erreur stockage: {e}")
            import traceback
            traceback.print_exc()
            return False

        

class Historique(models.Model):
    fichier = models.ForeignKey(Fichier, on_delete=models.CASCADE)
    date_traitement = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True)
    partage = models.BooleanField(default=False)
    
    # Nouveaux champs ajoutés
    méthode_anonymisation = models.CharField(max_length=255, blank=True, null=True)
    statut = models.CharField(max_length=20, choices=[
        ('En cours', 'En cours'),
        ('Terminé', 'Terminé'),
        ('Échoué', 'Échoué'),
    ], default='En cours')

    def __str__(self):
        return f"Historique {self.fichier.nom_fichier} - {self.date_traitement}"

class Métriques(models.Model):
    historique = models.ForeignKey(Historique, on_delete=models.CASCADE)
    lignes_traitees = models.IntegerField()
    colonnes_anonymisees = models.IntegerField()
    taux_anonymisation = models.FloatField()
    score_securite = models.FloatField()

    def __str__(self):
        return f"Métriques {self.historique.id}"

class RapportConformité(models.Model):
    historique = models.ForeignKey(Historique, on_delete=models.CASCADE)
    analyse_risques = models.TextField()
    recommandations = models.TextField()
    conformite = models.CharField(max_length=100, default="Conforme RGPD/CDP")

    def __str__(self):
        return f"Rapport {self.historique.id}"
    
