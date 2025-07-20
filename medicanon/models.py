from django.contrib.auth.models import AbstractUser
from django.db import models

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
    fichier = models.FileField(upload_to='fichiers/') 
    fichier_anonymise = models.FileField(
        upload_to='fichiers_anonymises/',
        null=True,
        blank=True,
        help_text="Fichier après anonymisation"
    )
    date_import = models.DateTimeField(auto_now_add=True)
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
    
    def get_download_file(self):
        """Retourne le fichier à télécharger (anonymisé si disponible, sinon original)"""
        if self.fichier_anonymise and self.statut == 'Anonymisé':
            return self.fichier_anonymise
        return self.fichier
    
    def get_download_filename(self):
        """Retourne le nom du fichier à télécharger"""
        if self.fichier_anonymise and self.statut == 'Anonymisé':
            return f"anonymized_{self.nom_fichier}"
        return self.nom_fichier

class Données(models.Model):
    fichier = models.ForeignKey(Fichier, on_delete=models.CASCADE)
    cle = models.CharField(max_length=255)
    valeur = models.TextField()
    sensible = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cle}: {self.valeur}"

class RègleAnonymisation(models.Model):
    nom = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=[
        ('Suppression', 'Suppression'),
        ('Pseudonymisation', 'Pseudonymisation'),
        ('Généralisation', 'Généralisation'),
        ('Hachage', 'Hachage'),
    ])
    parametres = models.JSONField(default=dict)

    def __str__(self):
        return self.nom

class DonnéesRègleAnonymisation(models.Model):
    donnees = models.ForeignKey(Données, on_delete=models.CASCADE)
    regle = models.ForeignKey(RègleAnonymisation, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('donnees', 'regle')

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
    
