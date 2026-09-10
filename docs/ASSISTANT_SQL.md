# HAKIMO : GPT écrit le SQL

## Parcours
`/assistant/message` appelle `run_sql_assistant`. GPT écrit un SELECT,
FastAPI valide sa structure et l'exécute dans Neon en lecture seule.
GPT reçoit les annonces et choisit leurs références et leur ordre avec
`presenter_selection`. Le serveur construit le tableau avec les données
effectivement reçues ; il refuse uniquement les références inventées.
Il n'applique aucun filtre métier ni classement par similarité après GPT.
Le budget, la zone, la vente et le choix final relèvent du prompt de GPT.

## Périmètre SQL
La première version permet les recherches de lignes, filtres et tris :
```sql
SELECT id FROM public.annonces
WHERE quartier_zone ILIKE '%Saaba%' AND prix_fcfa <= 6000000
ORDER BY prix_fcfa / NULLIF(superficie_m2, 0)
LIMIT 100
```
Les détails sont joints automatiquement à partir des IDs trouvés. Les IDs
techniques ne sont pas transmis au modèle ; il reçoit les références publiques.
Les résultats sont un échantillon limité, jamais une mesure exhaustive du marché.
Les agrégats, jointures, sous-requêtes, aliases, casts et fonctions arbitraires
ne sont pas pris en charge. Le modèle reçoit ce contrat et peut corriger un SQL refusé.
La relecture des références existantes et les quartiers proches disposent de
deux outils auxiliaires, sans MCP et sans classement.

## Protection de la base
Une grammaire SQL fermée est vérifiée par SQLGlot, puis la requête est réémise
en dialecte PostgreSQL. Une seule table et les colonnes documentées sont accessibles.
Chaque transaction est READ ONLY. Le search_path du SQL modèle est pg_catalog.
Les contacts, comptes utilisateurs et catalogues ne sont pas accessibles au SQL modèle.
LIMIT est plafonné à 100 et quatre consultations maximum sont autorisées par message.
Le garde-fou PostgreSQL de 20 secondes protège les ressources d'une requête ;
ce n'est pas le retour d'un timeout de conversation ou MCP.
Les erreurs SQL sont résumées sans publier les détails de connexion.
Les champs de carte sont normalisés avec les fonctions existantes ; aucune
annonce n'est supprimée, ni reclassée à cette étape.

Pour une défense supplémentaire, configurer ASSISTANT_DATABASE_URL avec un rôle
dédié possédant uniquement SELECT sur les colonnes utilisées :
```sql
CREATE ROLE hakimo_reader LOGIN;
GRANT USAGE ON SCHEMA public TO hakimo_reader;
GRANT SELECT (id, url, date_publication, premiere_collecte, type_bien,
    type_bien_normalise, quartier_zone, superficie_m2, prix_fcfa,
    statut_document, resume_court, texte_nettoye)
ON public.annonces TO hakimo_reader;
ALTER ROLE hakimo_reader SET default_transaction_read_only = on;
```
Définir son mot de passe séparément dans l'administration Neon, puis renseigner
la connexion côté hébergeur. Ne jamais donner cette connexion à GPT.
Sans ASSISTANT_DATABASE_URL, DATABASE_URL est utilisé avec les mêmes protections SQL
et transactionnelles. Aucune migration des annonces n'est nécessaire.

## Déploiement et compatibilité
Installer requirements.txt puis démarrer app.main:app. Le Dockerfile existant
utilise déjà ce point d'entrée. app.combined:http_app reste compatible pour
l'hébergement existant, mais le site n'utilise plus son endpoint MCP.
Le module MCP historique est conservé pour les intégrations externes.
L'interface conserve son design et ses huit colonnes. data_used active les résultats ;
mcp_used reste false. L'historique ancien reste lisible avec le champ historique.
Les alertes réutilisent la description consolidée choisie par GPT.
Les contacts continuent à passer par les routes authentifiées existantes.

## Validation
Les tests couvrent SQL dangereux, ordre décidé par GPT, correction SQL,
références inventées, pannes et salutation sans base.
La CI exécute également les requêtes sur un PostgreSQL jetable, sans clé OpenAI
et sans toucher Neon. Une validation réelle avec la clé de l'hébergement reste
nécessaire avant d'affirmer la qualité et la vitesse du nouveau parcours.

Sources : https://developers.openai.com/api/docs/guides/function-calling
et https://www.postgresql.org/docs/current/sql-set-transaction.html
