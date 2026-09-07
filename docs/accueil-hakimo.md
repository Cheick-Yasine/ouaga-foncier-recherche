# Accueil et espace HAKIMO

La navigation propose Accueil, Parlez-nous de votre projet immobilier, Mes alertes,
Favoris, Historique et les ressources. Le bouton du volet conserve ses trois états
(ouvert, historique en plein écran, masqué). Accueil et discussion partagent les
raccourcis et statistiques, sans perdre une conversation en changeant de page.
Les favoris, alertes et conversations existants gardent leurs clés de stockage.
Les alertes se relancent manuellement ; aucune notification n'est annoncée.

## Chiffres du dernier mois

`GET /market/stats` lit le pool complet, sans la limite de 2 000 annonces de la
recherche, et profite du cache des candidats pendant cinq minutes. Les totaux
portent sur les publications datées dans les 30 derniers jours, à Ouagadougou,
hors locations, annonces mixtes, demandes d'achat explicites et biens signalés
vendus. Les publications avec la même URL ne sont comptées qu'une fois.

La date de publication ISO exploitable fait foi : une date de collecte récente
ne transforme pas une vieille publication en annonce récente. Les dates absentes,
relatives ou illisibles et les dates futures sont exclues. L'interface le précise.
La moyenne arithmétique porte seulement sur les prix totaux et surfaces positifs
et finis. Elle affiche la taille de ce sous-ensemble. Le quartier principal est
calculé sur les quartiers renseignés ; Ouagadougou seul n'est pas un quartier.
Une indisponibilité serveur est signalée et peut être réessayée, sans faux zéro.

## Publications et compte

Les résultats MCP contiennent `facebook_url`, validée côté serveur ; « Voir »
utilise cette URL comme `href`. `POST /annonces/liens` retrouve les liens publics
des anciens favoris, sans contact ni texte. Les anciens liens applicatifs restent
compatibles. Facebook garde ses propres règles d'accès aux groupes/publications.
Les contacts restent soumis à l'authentification existante.

`PATCH /auth/me` modifie le nom et, facultativement, le mot de passe du seul
utilisateur connecté. Le mot de passe actuel est obligatoire. La modification
garde le même identifiant utilisateur et donc les collections existantes. Un
changement de mot de passe invalide les autres sessions, dans la même transaction.
Aucune migration SQL n'est nécessaire.
