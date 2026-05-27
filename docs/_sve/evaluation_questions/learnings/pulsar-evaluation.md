Le dataset olist est bien connu des LLMs, c'est pas l'idéal ...
On explique pas vraiment comment utiliser le tool query_cube, je pense que la connaissance de l'outil de cube est importante. ce n'est pas forcément un problème (se baser sur l'intelligence de l'outil, sans surcharger le contexte, c'est le must. Mais attention en cas de changement de modèle)


# Question S2

- Le cube customers a du être corrigé pour cette question, afin d'inclure la mesure permettant le distinct customer_unique_id (un bon modèle sémantique est nécessaire...)
- j'ai laissé la mesure 'count', pour voir si le LLM faisait bien la levé de doute
- correspondance Sao Paulo -> brezilian state code est dans la knowledge de Sonnet 4.6


# Question M1 - What are the top 10 product categories by total revenue?

Sans instructions système clair, l'agent peut choisir d'utiliser sa connaissance interne pour les traductions plutôt que ce qui existe dans les données

-> ajout au prompt :
"""6. If your answer includes any information not sourced directly from the query results (e.g. translations, labels, or context drawn from your own knowledge), disclose this explicitly before presenting the result. Still provide the answer — transparency is the goal, not refusal."""

# Question M2

No chat suggestion implemented in our agent / UI

# Question M3

- OK

# Question M3b
- nickel
- aprentissage perso : la mesure 'count' côté cube 'qui génère toujours COUNT(DISTINCT primary_key)'

# Question M5

voir eva_M5_deep_dive.md
-> on a une problématique de grain dans la modélisation marts (review sur orders, qui contient plusieurs items)
-> le modèle sémantique ne permet pas non plus de faire des approx (on a les métriques ou on les a pas)

-> j'ai choisi pour l'instant :
- de décrire le grain et les join path dans les descriptions des cubes (pas la manière de faire, c'est un détournement...)
- de briefer l'agent pour qu'il identifie correctement les problématiques et ambiguité, les exposer et ne pas répondre si c'est infaisable
- sonnet est suffisamment intelligent, si on lui dit : je peux faire une requête SQL sur Snow, définissons ensemble les approx à faire et écrit moi la requete, c'est très naturel. Par contre on copie colle

=> GROS TRAVAIL SUR CE QU'ON DEVRAIT EXPOSER (les vues et pas les cubes) ET DONC DES OUTILS DE L'AGENT ...
=> A CREUSER AUSSI, IL Y A UNE SQL API de cube, pas mal pour aborder les choses plus complexes ?
