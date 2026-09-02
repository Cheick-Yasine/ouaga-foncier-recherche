# Étape 2 — Audit de la table `annonces` sur Neon

## But

Observer le schéma réel et la qualité générale de la table sans modifier les données.

L'audit collecte uniquement :

- les noms et types des colonnes ;
- les contraintes et index ;
- le nombre total de lignes ;
- le nombre de valeurs manquantes par colonne ;
- la première collecte et la dernière mise à jour ;
- les valeurs les plus fréquentes pour le type de bien, le quartier et le document.

Aucun texte d'annonce, numéro WhatsApp ou mot de passe n'est exporté.

## Schéma attendu d'après le dépôt ETL

La table produite par `ouaga-foncier-etl` contient :

- `id` comme clé primaire ;
- `groupe_nom`, `url`, `date_publication`, `date_incertaine` ;
- `type_bien`, `quartier_zone`, `superficie_m2`, `prix_fcfa` ;
- `statut_document`, `contacts_whatsapp`, `mots_cles_pertinents` ;
- `resume_court`, `texte_nettoye` ;
- `premiere_collecte`, `derniere_maj`.

## Point important déjà identifié

`date_publication` est actuellement de type `TEXT`. Ce type est fragile pour le filtre obligatoire des sept derniers jours. Une étape ultérieure devra :

1. créer une vraie colonne temporelle normalisée ;
2. convertir uniquement les dates valides ;
3. conserver l'indicateur `date_incertaine` ;
4. indexer la nouvelle colonne ;
5. ne jamais supprimer la colonne d'origine avant validation.

## Exécution locale

Dans PowerShell, après avoir configuré le fichier local `.env` :

```powershell
python -m scripts.audit_neon_schema --output reports/neon-schema-audit.json
```

Le script place la transaction PostgreSQL en lecture seule.

## Exécution dans GitHub Actions

Le workflow manuel **Audit Neon** nécessite un secret GitHub nommé exactement `DATABASE_URL`.

Le rapport est proposé comme artefact téléchargeable pendant sept jours et n'est jamais ajouté automatiquement au dépôt.
