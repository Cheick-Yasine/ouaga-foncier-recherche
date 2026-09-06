# HAKIMO — HAKILAB IMMOBILIER

HAKIMO est l’interface conversationnelle. Le moteur `/search` et les outils MCP restent disponibles. Le logo HAKILAB fourni est conservé dans `app/static/hakilab-logo.png`.

## Présentation

- Une recherche affiche directement la recommandation puis le tableau existant : Rang, Localisation, Superficie, Prix, Prix / m², Document, Contact, Actions. Le texte du modèle ne recopie ni les annonces ni les critères.
- Une publication copiée reçoit un résumé développé en français simple : prix, points forts, éléments à vérifier et justification des alternatives. Le gras et les puces sont rendus comme des éléments DOM ; aucun HTML du modèle n’est exécuté. L’ancien encadré technique d’analyse est supprimé.
- Le volet latéral contient seulement l’historique et peut s’étendre à toute la page ou disparaître complètement. Son bouton reste accessible dans le bandeau supérieur ; le choix est conservé dans le navigateur. Les enregistrements et surveillances s’ouvrent depuis les boutons du bandeau supérieur. L’accueil contient uniquement les propositions de conversation, sans slogan ni flèches.
- Le menu Apparence permet les modes clair, sombre ou système et quatre couleurs. Ce choix reste dans le navigateur.
- Après connexion, les contacts du tableau se chargent automatiquement en une seule requête `POST /annonces/selection`. Le lien Voir redirige vers la publication Facebook d’origine via `GET /annonces/{reference}/source`, sans fenêtre de détail intermédiaire.

Les conversations, enregistrements et surveillances restent dans ce navigateur, avec une clé distincte par compte. Les contacts chargés ne sont pas persistés avec les résultats ni envoyés au modèle. Les anciens identifiants d’enregistrements restent utilisables après connexion. Les surveillances sont manuelles : Vérifier relance la recherche. Aucun compteur de nouvelles annonces ni notification automatique n’est affiché.

## Recommandations

Le budget maximum reste un plafond strict. Les critères explicites de quartier, type, document, proximité et viabilité sont prioritaires ; une superficie demandée favorise les biens comparables. Une demande générale de bonne affaire privilégie les parcelles courantes aux grands terrains agricoles.

À critères comparables, les annonces avec documentation, eau, électricité et proximité renseignées sont prioritaires. Viennent ensuite la complétude des informations utiles et leur disponibilité annoncée, puis le prix au m² le plus bas et le prix total. Le prix n’annule donc plus l’absence de documentation ou d’équipements. Si aucune annonce n’a ces informations, le tableau reste consultable sous « Offres à compléter », sans carte de recommandation.

Il s’agit d’informations annoncées : une mention n’est pas une vérification, une APFR déposée n’est pas délivrée et une conduite proche n’est pas un raccordement. Les documents en cours, négations et équipements futurs ne comptent pas comme disponibles. Le score technique ne constitue pas une estimation immobilière ni une probabilité.

## Publications et comparaisons

L’outil d’évaluation reçoit le texte original fourni par l’utilisateur, après retrait des contacts, plutôt qu’une réécriture des nombres par le modèle. Les montants tels que 3 500 000, 3.500.000 ou 3 millions 500 restent 3 500 000 FCFA. Les préférences de budget restent séparées du prix vendeur.

Les comparables servant de repère de prix proviennent du même quartier, du même type de bien et de surfaces proches (±25 %). Les alternatives peuvent venir de zones proches, jusqu’à 8 km entre repères cartographiques sourcés, avec la distance approximative et un lien vers la carte dans la colonne Localisation. Elles doivent apporter un avantage réel et respecter les critères. Les règles et les licences des données sont dans [cartographie.md](cartographie.md). Un lieu explicite absent du référentiel, tel que Roumtenga, reste une mention littérale, sans voisinage inventé. Une localisation à l’échelle de Ouagadougou seule ne suffit pas pour une comparaison locale. La publication analysée et ses republications sont écartées.

Un repère médian nécessite au moins trois comparables. Sinon l’assistant explique simplement qu’il manque des éléments pour conclure sur le prix. Aucun autre quartier n’est proposé silencieusement comme équivalent.

Les suggestions de comparaison sélectionnent deux annonces du même quartier. Si l’utilisateur désigne explicitement des annonces de quartiers différents, son choix est conservé et la comparaison ne sert pas de repère de prix local.

## Exécution et vérification

Un seul appel MCP est autorisé par message, sans questionnaire préalable. Le délai MCP reste illimité. L’authentification des contacts et liens source est conservée.

Les tests couvrent notamment les prix originaux, budgets, classement des annonces complètes, équipements futurs, comparaisons locales, liens Facebook, contacts groupés et contrat du tableau.

Dans Git Bash, activer l’environnement avec `source .venv/Scripts/activate` dans chacun des deux terminaux. Lancer `python -m uvicorn app.mcp_server:http_app --host 127.0.0.1 --port 8001` puis, dans l’autre terminal, `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`. Le site s’ouvre sur le port 8000.
