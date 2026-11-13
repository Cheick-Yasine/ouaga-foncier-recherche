# Prix médians au m² par quartier

Le calcul mélange volontairement tous les types de biens présents dans
`public.annonces`. Il produit une médiane du prix annoncé au m², sans
séparer terrains, parcelles, maisons ou autres catégories.

## Calcul quotidien

Le traitement est :

```bash
docker compose run --rm --no-deps api python scripts/refresh_neighborhood_prices.py
```

Il lit la table finale `public.annonces`, ignore les annonces placées dans la
corbeille, les locations et les annonces hors périmètre, regroupe les variantes
de quartiers sur les noms du catalogue de 201 quartiers et conserve seulement
des agrégats. Une annonce sans date de publication exploitable n'est pas prise
en compte. Une annonce sans prix ou sans superficie reste comptée dans le
nombre d'annonces du quartier, mais ne participe pas à la médiane.

La migration `db/migrations/006_neighborhood_price_daily.sql` est appliquée
par le traitement si nécessaire. Le traitement est idempotent : une nouvelle
exécution le même jour met à jour le snapshot de cette journée.

## Programmation sur le VPS

Après le premier lancement manuel réussi, créer le dossier de logs :

```bash
mkdir -p /home/cheick/hakili_immobilier/logs
```

Puis ajouter cette ligne à la crontab de l'utilisateur qui exécute Docker
(`crontab -e`) :

```cron
0 2 * * * cd /home/cheick/hakili_immobilier && /usr/bin/docker compose run --rm --no-deps api python scripts/refresh_neighborhood_prices.py >> /home/cheick/hakili_immobilier/logs/neighborhood-prices.log 2>&1
```

Le calcul est lancé à 02:00 selon le fuseau horaire du VPS. Pour vérifier le
fuseau : `timedatectl`.

## API et interface

- `GET /market/neighborhood-prices` renvoie le dernier snapshot quotidien.
- Les marqueurs géolocalisés affichent le prix médian au survol.
- La comparaison utilise les quartiers sélectionnés, y compris ceux sans
  coordonnées cartographiques.
- Le résultat indique le nombre d'annonces retenues et le nombre de prix au m²
  effectivement calculés.

Les montants sont des prix demandés dans les annonces, pas des prix de vente
réellement conclus. Le mélange des types de biens rend l'indicateur global
pratique pour un premier repère, mais moins précis qu'une comparaison à type
de bien constant.
