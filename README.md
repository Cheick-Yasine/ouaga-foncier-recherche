# Ouaga Foncier — Recherche immobilière

Plateforme de recherche intelligente d'annonces immobilières collectées autour de Ouagadougou.

## Objectif

L'utilisateur décrit le terrain, la parcelle ou la maison qu'il recherche. La plateforme transforme cette description en critères structurés, interroge la base PostgreSQL hébergée sur Neon et classe les annonces les plus pertinentes.

## Règles essentielles

- filtrer les annonces sur 7 jours, 1 mois ou 3 mois, avec 1 mois par défaut, et afficher leur ancienneté ;
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
- automatisation : GitHub Actions ;
- intégration IA : GPT utilise les outils MCP de recherche et d’analyse.

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

## Assistant GPT → MCP → Neon

L’assistant appelle les outils MCP. Le moteur existant normalise les quartiers
à partir du référentiel, filtre les annonces puis classe les résultats.
GPT formule ses conseils à partir de ces résultats. Le SQL généré par GPT
et le catalogue préparé séparé ne sont plus utilisés par la conversation.

Les ventes de maisons, parcelles et terrains dans le périmètre sont conservées.
Les locations, biens annoncés non lotis et annonces sans prix ET sans superficie
sont exclus. Une seule valeur manquante ne suffit pas à exclure une annonce.

Configuration locale :
```dotenv
OPENAI_API_KEY=votre_cle_locale
ASSISTANT_MODEL=gpt-5.6-luna
DATABASE_URL=postgresql://...
MCP_SERVER_URL=http://127.0.0.1:8001/mcp
```

Lancer le MCP et le site dans deux terminaux :
```bash
python -m uvicorn app.mcp_server:http_app --host 127.0.0.1 --port 8001
```
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Sur Render, `app.combined:http_app` héberge déjà le site et le MCP.
Les tables préparées et le code SQL sont conservés pour référence, sans supprimer
les données. Leur documentation décrit l’architecture précédente.
L’interface, les comptes et les favoris restent en place.

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
