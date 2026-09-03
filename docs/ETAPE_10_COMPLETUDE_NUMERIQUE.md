# Étape 10 révisée — Filtrage de la complétude numérique

## Décision

L'imputation des prix et superficies est supprimée.

Le moteur de recherche utilisera uniquement les annonces qui possèdent à la fois :

- un prix réellement observé ;
- une superficie réellement observée et strictement positive.

Aucune moyenne ou valeur de remplacement n'est calculée.

## Pourquoi cette règle

Le moteur doit comparer la description de l'utilisateur aux annonces selon plusieurs
dimensions, notamment le prix et la superficie. Une valeur artificielle pourrait
rendre une annonce faussement proche de la demande.

Le filtrage garantit que :

- le prix affiché vient réellement de l'annonce ;
- la superficie affichée vient réellement de l'annonce ;
- le prix au m² est calculé uniquement avec deux valeurs observées ;
- les scores de proximité numérique ne reposent pas sur des estimations fabriquées.

## Motifs d'exclusion

Chaque annonce incomplète reçoit un seul motif :

- `prix_manquant` ;
- `superficie_manquante` ;
- `prix_et_superficie_manquants` ;
- `superficie_non_positive`.

Une annonce `complete` reste dans la future base de recherche.

## Conservation de la base brute

« Exclure » signifie retirer l'annonce du jeu de données préparé pour la recherche.
La ligne originale n'est jamais supprimée de `public.annonces` dans Neon.

Cela permet de la réintégrer plus tard si le collecteur obtient un prix ou une
superficie lors d'une nouvelle publication ou mise à jour.

## Conséquence attendue

D'après l'audit précédent :

- 3 401 annonces étaient disponibles avant ce filtre ;
- 2 710 possédaient déjà une cible prix au m² réellement observée ;
- environ 691 annonces devraient donc être écartées de la base de recherche.

Le nouvel audit calculera les nombres exacts et séparera les différents motifs.

## Confidentialité

Le workflow manuel **Audit complétude numérique** utilise Neon en lecture seule.
La trace détaillée reste temporaire dans le runner. L'artefact publié contient
uniquement des statistiques agrégées, sans prix, superficie, texte, contact, URL ou
identifiant individuel.
