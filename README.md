# Ouaga Foncier — Recherche immobilière

Plateforme de recherche intelligente d'annonces immobilières collectées autour de Ouagadougou.

## Objectif

L'utilisateur décrit le terrain, la parcelle ou la maison qu'il recherche. La plateforme transforme cette description en critères structurés, interroge la base PostgreSQL hébergée sur Neon et classe les annonces les plus pertinentes.

## Règles essentielles

- conserver les annonces quelle que soit leur date et afficher leur date lorsqu’elle existe ;
- séparer les contraintes obligatoires des préférences ;
- ne jamais dépasser un budget exprimé comme maximum ;
- ne jamais inventer un prix, une superficie ou un document absent ;
- regrouper les doublons et republications ;
- effectuer un dernier contrôle sémantique avec `gpt-4o-mini` ;
- ne transmettre à OpenAI aucun contact, e-mail, lien Facebook ou identifiant ;
- expliquer la raison du classement de chaque résultat.

## Socle technique

- API : FastAPI ;
- base : PostgreSQL sur Neon ;
- recherche textuelle : PostgreSQL Full Text Search ;
- recherche sémantique prévue : pgvector ;
- tests : pytest ;
- automatisation : GitHub Actions.

## Installation locale sous Windows

```powershell
git clone https://github.com/Cheick-Yasine/ouaga-foncier-recherche.git
cd ouaga-foncier-recherche
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Ouvrez ensuite le fichier `.env`, ajoutez l’URL PostgreSQL fournie par Neon et votre clé `OPENAI_API_KEY`. Sans clé OpenAI, l’application conserve automatiquement le classement local.

> Ne publiez jamais la véritable valeur de `DATABASE_URL` dans GitHub, une capture d'écran ou un message.

## Lancer l'API

```powershell
uvicorn app.main:app --reload
```

Adresses utiles :

- API : http://127.0.0.1:8000
- documentation interactive : http://127.0.0.1:8000/docs
- santé de l'API : http://127.0.0.1:8000/health
- test de Neon : http://127.0.0.1:8000/health/database

## Lancer les tests

```powershell
python -m pytest
```

## Auditer la table Neon en lecture seule

Après avoir configuré `.env` :

```powershell
python -m scripts.audit_neon_schema --output reports/neon-schema-audit.json
```

Le rapport contient la structure, les index, le volume et les valeurs manquantes, mais aucun texte d'annonce ni numéro WhatsApp. Consultez [la documentation de l'étape 2](docs/ETAPE_2_AUDIT_NEON.md).

## Sécurité de Neon

La vraie `DATABASE_URL` est enregistrée uniquement :

1. dans le fichier local `.env`, ignoré par Git ;
2. dans les variables sécurisées de l'hébergeur lors du déploiement ;
3. éventuellement dans GitHub Actions Secrets si un workflow doit accéder à Neon.

Le dépôt contient seulement `.env.example`, sans identifiants réels.

## Étapes prévues

1. Socle FastAPI et connexion Neon.
2. Audit du schéma existant de la table `annonces`.
3. Normalisation des quartiers, types de biens et documents.
4. Moteur de filtres métier sur toutes les annonces admissibles.
5. Recherche plein texte PostgreSQL.
6. Filtre sémantique final avec `gpt-4o-mini`, sur un lot anonymisé.
7. Score métier, déduplication et explications.
8. Interface de recherche.
