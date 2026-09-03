# Serveur MCP — Ouaga Foncier

Le serveur MCP rend le moteur immobilier utilisable par un client compatible MCP, notamment ChatGPT ou Codex.

## Outils disponibles

- `interpreter_recherche` : transforme une description en critères structurés ;
- `rechercher_annonces` : classe et filtre les annonces avec le moteur métier puis `gpt-4o-mini` ;
- `search` : interface de recherche compatible avec les clients MCP ;
- `fetch` : récupère le détail public d’un résultat à partir de sa référence opaque.

## Confidentialité

Le MCP est strictement en lecture seule.

Il ne retourne jamais :

- le contact ou le numéro WhatsApp ;
- l’identifiant Facebook brut ;
- l’URL Facebook ;
- une adresse e-mail présente dans le texte.

Les textes sont nettoyés et les identifiants sources sont remplacés par des références opaques. Le filtre `gpt-4o-mini` conserve sa propre anonymisation avant l’appel à OpenAI.

## Lancement local

Installez les dépendances puis lancez :

```powershell
python -m pip install -r requirements.txt
uvicorn app.mcp_server:http_app --host 127.0.0.1 --port 8001
```

Le point d’entrée MCP streamable HTTP est alors :

```text
http://127.0.0.1:8001/mcp
```

L’API web continue séparément sur le port 8000 :

```powershell
uvicorn app.main:app --reload
```

## Configuration

Le serveur utilise les mêmes variables que l’application :

- `DATABASE_URL` pour lire Neon ;
- `OPENAI_API_KEY` pour le filtre final ;
- `LLM_MODEL=gpt-4o-mini` pour conserver le modèle choisi.

Sans clé OpenAI, les outils restent fonctionnels grâce au classement local.

## Déploiement

Cette étape fournit un serveur MCP fonctionnel en local. Avant de rendre l’URL accessible sur Internet, il faudra ajouter l’authentification distante, HTTPS, une limite de débit et un suivi des appels.
