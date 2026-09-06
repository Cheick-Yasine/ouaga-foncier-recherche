# Repères cartographiques de HAKIMO

Les analyses utilisent un référentiel local de **71 repères** de quartiers et
localités autour de Ouagadougou, consulté le **6 septembre 2026**. Il sert à
calculer la proximité entre zones. Il ne donne ni les coordonnées d’une parcelle,
ni sa disponibilité, ni le temps de trajet. Aucun appel de géocodage n’est fait
pendant une conversation et aucune position de l’utilisateur n’est collectée.

## Sources et licences

- `app/data/neighborhoods_geonames.json` : 67 points du fichier Burkina Faso de
  [GeoNames](https://download.geonames.org/export/dump/BF.zip), sous
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Attribution : **GeoNames**. Les coordonnées WGS84 sont conservées ; la sélection
  des lieux, les noms d’affichage et certains alias sont adaptés au référentiel de
  l’application. Le nom source, le code de lieu et l’identifiant GeoNames sont
  conservés dans chaque entrée. Une fiche est consultable à
  `https://www.geonames.org/{source_id}/`.
- `app/data/neighborhoods_osm.json` : quatre repères complémentaires de
  [OpenStreetMap](https://www.openstreetmap.org/copyright), sous
  [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
  Attribution : **© OpenStreetMap contributors**. Ce fichier dérivé reste sous
  ODbL 1.0 et est distribué avec le code. Les identifiants, types et noms source
  sont conservés. Les points de Bassinko, Yagma et Paglayiri sont des nœuds de
  lieu ; Karpala utilise le centre de la boîte englobante de sa zone OSM, pas
  un centre administratif officiel.

Les deux sources sont conservées dans des fichiers distincts avec leur licence.
L’interface crédite les deux fournisseurs sous les tableaux avec des distances.
Le lien « Voir sur la carte » place un repère sur le quartier de l’alternative.

La sélection évite de confondre les villages homonymes avec les quartiers
urbains : Tanghin, Kossodo, Ouidi, Samandin, etc. Les entrées urbaines GeoNames
`PPLX` sont utilisées, pas les villages éloignés de même nom. Un nom ambigu comme
Sabtenga n’a pas reçu arbitrairement un point. Une commune explicitement précisée
dans une annonce est conservée : « Tanghin (Saaba) » n’emprunte pas le point
du quartier Tanghin de Ouagadougou.

Le référentiel ne couvre pas tous les quartiers, extensions ou villages.
Un nom inconnu reste inconnu ; aucun alias approximatif n’est inventé. Une zone
trop large (« Ouagadougou », « Centre Ville ») ne devient pas un quartier. Ce
référentiel n’élargit pas le périmètre de collecte des annonces.

## Distances et alternatives

`app/neighborhood_geo.py` calcule une distance à vol d’oiseau avec la formule de
Haversine sur les coordonnées WGS84. Le rayon de recherche des alternatives est
de **8 km** entre repères, un choix de produit modifiable via `NEARBY_RADIUS_KM`.
Le filtre s’applique avant l’arrondi à un chiffre après la virgule. Il ne prétend
pas que les limites des quartiers se touchent.

Deux annonces dans le même quartier portent « Même quartier », sans afficher
« 0 km » entre les parcelles. Une alternative voisine porte, par exemple,
« ≈ 5 km de Saaba ». Le tableau précise que la distance est approximative, entre
quartiers, en ligne droite, et qu’un trajet routier peut être plus long.

Une alternative doit être du même type, de la même famille de terrain et d’une
surface proche (±25 % de la surface demandée). Elle respecte le budget et les
documents, équipements et proximités demandés. Elle doit mentionner un document,
préserver les informations positives de l’annonce analysée et apporter un prix
au m² inférieur ou des informations plus complètes. Un document différent n’est
pas présenté comme juridiquement meilleur. Un surcoût n’est accepté que dans un
budget utilisateur explicite, avec son montant et le compromis indiqués ; sans
budget explicite, le prix total de l’annonce analysée sert de plafond.

Les offres complètes restent prioritaires, puis les offres du quartier d’origine
avant ses voisins. Le classement qualité/prix départage les offres dans ces
groupes. Si l’utilisateur exige un seul quartier, la recherche ne s’élargit pas.
Sans avantage établi, l’outil ne présente pas une offre comme meilleure.

Le repère de prix de l’analyse utilise uniquement les offres du **même quartier**,
de même type et de surface proche. Les voisins ne modifient pas ce repère. Son
calcul interne utilise une médiane à partir de trois annonces dédupliquées ;
l’assistant explique seulement un « prix de repère des offres similaires ».
En l’absence d’un nombre suffisant d’offres, il ne conclut pas qu’un prix est bas
ou élevé. Le résumé en français simple sépare prix, points forts, éléments à
vérifier et avantage de l’alternative.

## Mettre à jour les repères

Télécharger à nouveau le fichier pays GeoNames et sélectionner les mêmes
identifiants avant de revoir manuellement les nouveaux lieux et leurs homonymes.
Pour OSM, cette requête [Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API)
retrouve les quatre objets retenus :

```overpass
[out:json][timeout:25];
(node(id:3296496974,9214406931,9587569259); way(27863585););
out center tags;
```

Conserver les licences et identifiants, mettre à jour la date de consultation,
et lancer les tests de géographie et d’analyse. Ne pas remplacer un point disparu
par un autre lieu de même nom sans vérifier sa zone. Pour un quartier non résolu,
il faut ajouter un point sourcé plutôt que deviner une distance.
