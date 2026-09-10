# Catalogue préparé HAKIMO

La table brute `public.annonces` reste intacte. `annonces_preparees` contient les ventes explicites de maisons, parcelles et terrains situés dans le référentiel existant de Ouagadougou et des environs. Les villas restent exclues, conformément au périmètre précédent.

Les locations, demandes, offres retirées, zones éloignées connues et cas ambigus sont écartés. Le référentiel n'est pas une garantie de géolocalisation : les localités inconnues et les indications contradictoires doivent être vérifiées. Aucune valeur numérique manquante n'est imputée. Deux publications ayant les mêmes caractéristiques restent distinctes.

Les séquences explicites `Superficie ... Prix ... Superficie ... Prix ...` sont séparées en lots stables avec leur source, leurs dates et leur lien Facebook. Les autres formats multiples sont isolés pour vérification. Les formulations de montant ambiguës (ex. « 3 millions 500 ») sont isolées, sans supposer leur valeur. Les prix unitaires explicites sont convertis pour la superficie annoncée. Les règles automatiques ne remplacent pas une vérification du vendeur.

`annonces_preparation_audit` conserve un motif par source, y compris celles exclues. `annonces_preparation_runs` conserve les bilans successifs. Les rapports GitHub ne contiennent ni contacts ni textes de publications.

## Exécution

1. `python -m scripts.prepare_annonces` : rapport de simulation, aucune écriture.
2. Examiner le nombre de ventes retenues et les motifs d'exclusion.
3. `python -m scripts.prepare_annonces --apply` : créer/actualiser les tables dérivées dans une transaction. La base brute n'est jamais modifiée. Un résultat vide annule l'opération.
4. Basculer l'assistant uniquement après cette exécution réussie. Le nouveau lecteur SQL refuse la table brute. Si un rôle SQL dédié est utilisé, lui accorder SELECT sur `annonces_preparees` avant la bascule, sans accès aux tables de comptes.

Le workflow « Préparer les annonces pour HAKIMO » fait uniquement une simulation sur push. Une application exige son lancement manuel avec `apply_changes=true`. Aucun rafraîchissement périodique n'est encore activé : il faudra programmer la commande après validation du premier catalogue, ou l'ajouter après chaque import ETL réussi.

La reconstruction est atomique, avec verrou empêchant deux actualisations concurrentes. Si elle échoue, le catalogue précédent reste accessible. Les favoris d'annonces désormais exclues ne sont pas remplacés par d'autres annonces. Les contacts gardent l'authentification existante.
