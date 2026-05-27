# M5 — Average review score per category (min 50 reviews)

## Question

What is the average review score by product category, for categories with at least 50 reviews? Use English names.

## Problématiques

1. Problème de grain : la review est à la maille ORDER, la catégorie est à la maille ITEM

  C'est le nœud central. Les données sous-jacentes ont deux grains incompatibles :

  ORDER_REVIEWS    → 1 ligne par ORDER   (review_id PK, order_id FK)
  ORDER_ITEMS      → 1 ligne par ITEM    (order_id + order_item_id PK)

  Un client commande des chaussures + un aspirateur dans le même order, laisse un score de 4 : à quelle catégorie appartient ce 4 ? Aux deux. La notion de "score par
  catégorie" n'existe pas nativement dans la structure — c'est une convention qu'on choisit d'appliquer.

  Ambiguïté implicite : la question "average review score by category" suppose silencieusement qu'une review est attribuée à toutes les catégories de l'order. Un bon système devrait signaler que c'est une approximation.

  ---
  2. Le fan-out : joindre order_reviews à order_items multiplie les lignes

  Jointure naïve order_reviews JOIN order_items ON order_id :

  review_id  order_id  score  |  item_id  category
  r1         o1        4      |  i1       shoes
  r1         o1        4      |  i2       vacuums

  → La review r1 apparaît 2 fois. Un AVG(review_score) calculerait la moyenne sur les lignes du join, pas sur les reviews distinctes. Avec des orders multi-items, les
  catégories d'articles vendus en bundle seraient sur-représentées et biaisées.

  Le SQL de référence dans l'évaluation contourne ça avec un CTE qui réduit à DISTINCT (order_id, category) avant de joindre les reviews. C'est une pré-agrégation manuelle
  que Cube ne génère pas automatiquement.

  ---
  3. L'ambiguïté du "review_count" dans le filtre HAVING ≥ 50

  "Categories with at least 50 reviews" — 50 quoi exactement ?

  - 50 reviews distinctes (orders ayant un score + au moins un item de la catégorie) — interprétation correcte
  - 50 lignes dans le join naïf (inflated par les orders multi-items) — silencieusement faux

  Si le join fan-out n'est pas géré, le filtre review_count >= 50 est biaisé : les catégories souvent achetées en bundle passent le seuil plus facilement.

  ---
  4. Ordres sans review (NULL scores)

  La table ORDER_REVIEWS ne contient pas nécessairement un enregistrement pour chaque order. Les ordres sans review sont absents → la moyenne ne porte que sur les ordres
  reviewés. C'est acceptable mais devrait être mentionné dans la réponse de l'agent.

  ---
  5. Le problème structurel Cube : chemin de jointure inexistant

  Le graphe de jointures actuel (arêtes dirigées) :

  order_reviews ──→ orders ──→ customers
  order_items   ──→ orders
  order_items   ──→ products ──→ product_category_name_translation

  Pour M5, Cube part de order_reviews (cube racine des mesures) et ne peut pas atteindre product_category_name_translation — orders n'a aucune arête sortante vers
  order_items.

  Mais même en ajoutant le maillon manquant (orders → order_items ou order_reviews → order_items), le fan-out du point 2 produirait un avg_review_score incorrect : Cube
  gère le fan-out pour count (via COUNT DISTINCT pk), pas pour avg qui génère AVG(review_score) sur toutes les lignes jointes.

  ---
  Synthèse

  ┌─────────────────────────────────────────────────┬─────────────────────────┬────────────────────────────────────────┐
  │                    Problème                     │         Nature          │        Contournable dans Cube ?        │
  ├─────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────┤
  │ Chemin de jointure manquant                     │ Structurel (modèle)     │ Oui — ajouter les joins                │
  ├─────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────┤
  │ Fan-out sur avg                                 │ Sémantique (grain)      │ Pas sans une vue dédiée ou un subQuery │
  ├─────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────┤
  │ Attribution d'une review à plusieurs catégories │ Conceptuel (convention) │ À documenter, pas à corriger           │
  ├─────────────────────────────────────────────────┼─────────────────────────┼────────────────────────────────────────┤
  │ HAVING count biaisé par fan-out                 │ Dérivé du fan-out       │ Idem                                   │
  └─────────────────────────────────────────────────┴─────────────────────────┴────────────────────────────────────────┘

  Conclusion : M5 est une requête cross-grain qui dépasse ce qu'un modèle Cube standard peut résoudre proprement avec ses primitives avg + one_to_many. La solution propre
  serait une vue Cube pré-jointe qui matérialise la relation (order_id, category) dédupliquée avant d'y attacher les scores — ce qui déplace la logique de dé-duplication
  dans le modèle sémantique plutôt que dans la requête de l'agent.

## Apprentissage
Beaucoup d'apprentissages ...

### on exploite pas cube comme on devrait
- les cubes ne doivent normalement pas être exposés en direct.
  - C'est une correspondance 1-1 avec les tables du modèle sous-jascent
  - on doit ensuite créer des vues 
- les requêtes via notre outil son

Pour avoir une réponse pertinente, les règles de résolution 
