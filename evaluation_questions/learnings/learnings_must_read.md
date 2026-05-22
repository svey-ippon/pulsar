Le dataset olist est bien connu des LLMs, c'est pas l'idéal ...
On explique pas vraiment comment utiliser le tool query_cube, je pense que la connaissance de l'outil de cube est importante. ce n'est pas forcément un problème (se baser sur l'intelligence de l'outil, sans surcharger le contexte, c'est le must. Mais attention en cas de changement de modèle)


# Question S2

Apprentissages :
- Le cube customers a du être corrigé pour cette question, afin d'inclure la mesure permettant le distinct customer_unique_id
- j'ai laissé la mesure 'count', pour voir si le LLM faisait bien la levé de doute

l'agent ne connait pas à priori la corrrespondance Sao Paulo - SP -> voir comment il réagirait si on lui donne Sao Paulo sans SP
distinction 


# Question M1 - détournement

Q = What are the top 10 product categories by total revenue?

l'agent commence par tenter cette requete :

```bash
cube-1  | UserError: 6c98ed4b-f196-4e8b-91dd-76bdb1584ffe-span-1 (66ms)
cube-1  | --
cube-1  | {
cube-1  |   "measures": [
cube-1  |     "order_items.total_revenue"
cube-1  |   ],
cube-1  |   "dimensions": [
cube-1  |     "product_category_name_translation.product_category_name_english"
cube-1  |   ],
cube-1  |   "filters": [],
cube-1  |   "timeDimensions": [],
cube-1  |   "limit": 10,
cube-1  |   "timezone": "UTC"
cube-1  | }
cube-1  | --
cube-1  | {}
cube-1  | Can't find join path to join 'order_items', 'product_category_name_translation'
cube-1  | Performing query: 4b8234ae-8201-4b11-8a98-7eb79dd8fe10-span-1
cube-1  | Executing SQL: 4b8234ae-8201-4b11-8a98-7eb79dd8fe10-span-1
```

il fait alors une requête sans la jointure (sans la traduction officielle) :

```bash
cube-1  | Performing query completed: 4b8234ae-8201-4b11-8a98-7eb79dd8fe10-span-1 (1195ms)
cube-1  | Load Request Success: 4b8234ae-8201-4b11-8a98-7eb79dd8fe10-span-1 (1232ms)
cube-1  | --
cube-1  | {
cube-1  |   "measures": [
cube-1  |     "order_items.total_revenue"
cube-1  |   ],
cube-1  |   "dimensions": [
cube-1  |     "products.product_category_name"
cube-1  |   ],
cube-1  |   "filters": [],
cube-1  |   "timeDimensions": [],
cube-1  |   "limit": 10,
cube-1  |   "cacheMode": "stale-if-slow",
cube-1  |   "timezone": "UTC"
cube-1  | }
```

il présente le résultat, sans mentionner sa traduction à la main.
-> on durcit le prompt pour honneteté du modèle
(n'est pas reproductible en l'état, on a corrigé le modèle)

ajout au prompt :

"""6. If your answer includes any information not sourced directly from the query results (e.g. translations, labels, or context drawn from your own knowledge), disclose this explicitly before presenting the result. Still provide the answer — transparency is the goal, not refusal."""
