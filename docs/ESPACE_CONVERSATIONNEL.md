# Espace conversationnel

L’accueil est désormais la conversation. Le moteur `/search` reste disponible pour les intégrations existantes. L’assistant appelle le serveur MCP configuré dans `MCP_SERVER_URL` ; il ne lit pas directement les contacts.

## Parcours

- Décrire un besoin, préciser les critères au fil des messages ou coller une publication de 6 000 caractères maximum.
- Obtenir une réponse argumentée, un récapitulatif des critères réellement utilisés et le tableau à huit colonnes : Rang, Localisation, Superficie, Prix, Prix / m², Document, Contact, Actions.
- Comparer deux ou trois annonces déjà affichées à partir de leurs références publiques ; elles sont rechargées et gardent l’ordre demandé.
- Consulter le texte complet et un seul contact après connexion. Les anciennes annonces enregistrées avec un identifiant interne restent consultables après authentification.
- Retrouver les conversations, enregistrements et surveillances dans le volet latéral. Le bouton d’agrandissement étend ce volet à toute la page ; sur mobile le volet s’ouvre depuis le menu.

Les conversations et enregistrements restent dans le navigateur, sous une clé distincte pour chaque compte. Il n’y a pas de synchronisation entre appareils. Les nouveaux enregistrements ne persistent pas le contact révélé ni le lien WhatsApp. Les données anciennes sont conservées. Les surveillances se relancent à la demande par le bouton « Vérifier » ; le compteur compare les dix résultats renvoyés aux annonces déjà vues. Aucun envoi automatique de notification n’est annoncé ni implémenté dans cette version.

## Classement des bonnes affaires

Les critères explicites de localisation et de type restent prioritaires. Le budget maximum est un plafond strict : une annonce sans prix ou au-dessus du plafond est exclue. Pour une superficie demandée, les offres proches (rapport min/max d’au moins 0,8) sont prioritaires. Sans type demandé, les parcelles de taille courante passent avant les grands terrains.

L’indice de bonne affaire est une règle de classement, pas une estimation de valeur ou une probabilité :

| Élément | Poids |
| --- | ---: |
| Prix au m² relatif aux offres du même groupe | 40 % |
| Documentation annoncée | 40 % |
| Eau et électricité annoncées | 12 % |
| Proximités décrites | 8 % |

Les groupes distinguent la zone, les maisons, les parcelles, les terrains et les grands terrains (surface supérieure à 2 500 m² ou vocabulaire agricole). Quand une surface est demandée, le calcul relatif évite les surfaces sans rapport avec celle de chaque offre. Le prix le plus bas est préféré à qualité identique. Une annonce isolée peut recevoir des points de prix : cet indice ne permet donc pas, seul, d’affirmer une décote par rapport au marché. Les poids et le seuil de taille sont des choix de produit explicites, non une règle foncière.

Un document annoncé disponible reçoit plus de poids qu’une simple mention ; un dossier déposé reçoit peu de poids. Un récépissé ou un croquis ne devient pas un titre délivré. Les négations et mentions de travaux à venir ne rapportent pas de points de disponibilité. Un raccordement à proximité ne devient pas un raccordement sur place. Ces règles sont des heuristiques textuelles : aucun document ni équipement n’est vérifié physiquement.

## Publication copiée

`evaluer_annonce` calcule les éléments observables, recherche des comparables de même type, même zone normalisée et surface à ±25 %, et écarte la publication elle-même ainsi que ses republications détectées. Les hectares agricoles ne servent pas de référence aux petites parcelles.

Un repère médian demande au moins trois annonces comparables. Au-dessus ou en dessous de 10 % de cette médiane, le texte signale l’écart ; il ne s’agit que de prix demandés dans les annonces. La qualité des documents, l’accès et les particularités locales peuvent expliquer les écarts. Sans prix, surface ou comparables suffisants, la conclusion reste limitée. Les caractéristiques du vendeur ne sont pas imposées comme critères obligatoires aux alternatives ; les préférences déjà exprimées par l’utilisateur sont conservées.

## Comportement et confidentialité

Le modèle est invité à rechercher dès qu’il comprend l’intention immobilière, puis à recommander sans questionnaire obligatoire. Chaque tour autorise au maximum une exécution MCP, y compris si le modèle propose plusieurs appels dans la même réponse. Le résultat contient déjà le tableau ou l’analyse et les alternatives. Le délai MCP reste illimité, conformément au réglage demandé.

Les publications sont des données non fiables ; les instructions qu’elles contiennent doivent être ignorées. Les contacts, e-mails et liens externes sont retirés avant l’envoi au modèle. Les montants explicitement identifiés comme prix ou budget sont conservés afin de ne pas confondre 12 000 000 FCFA avec un téléphone.

## Vérification

Les tests couvrent les contraintes de budget, les documents déposés, les équipements absents ou prévus, le classement à qualité égale et différente, les grands terrains, les décimales, l’analyse des comparables, les republications, l’appel MCP unique, le contrat de l’interface et la protection des contacts.

Après récupération de cette branche, redémarrer les deux processus : le serveur MCP sur 8001 pour charger ses nouveaux outils et l’application sur 8000 pour charger la conversation. Les dépendances et les variables d’environnement ne changent pas.
