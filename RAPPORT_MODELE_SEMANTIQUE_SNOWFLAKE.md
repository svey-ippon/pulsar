# Rapport - Mise en place d'un modele semantique Snowflake

Date : 2026-05-29

## Contexte

Ce repository est un POC visant a evaluer differentes options pour developper un equivalent custom de Snowflake Intelligence, puis le comparer a Snowflake Intelligence.

La solution actuelle repose sur :

- une couche semantique Cube Core dans `pulsar_cube/cube/` ;
- un agent LangGraph dans `pulsar_cube/pulsar-agent/` ;
- une UI Streamlit dans `pulsar_cube/pulsar-ui/`, hors perimetre pour la suite de l'evaluation ;
- un dataset Olist charge dans Snowflake via `snowflake_setup/` ;
- un protocole d'evaluation qualite et cout dans `docs/evaluation/`.

Le flux actuel est :

```text
Streamlit -> pulsar-agent -> Cube Core -> Snowflake
```

L'objectif de la prochaine etape est de mettre en place une couche semantique cote Snowflake afin de rejouer la meme evaluation qualite/cout avec Snowflake Intelligence.

## Etat actuel du POC

### Donnees

Les donnees Olist sont chargees dans Snowflake dans :

```text
ECOMMERCE_DB.SILVER
```

Les tables principales sont :

- `ORDERS`
- `ORDER_ITEMS`
- `ORDER_PAYMENTS`
- `ORDER_REVIEWS`
- `CUSTOMERS`
- `SELLERS`
- `PRODUCTS`
- `PRODUCT_CATEGORY_NAME_TRANSLATION`
- `GEOLOCATION`

Le projet `snowflake_setup/` contient les schemas YAML source, les descriptions de tables/colonnes, et le script de chargement.

### Couche semantique Cube

La couche Cube est structuree en deux niveaux :

- `pulsar_cube/cube/model/cubes/` : objets prives contenant les joins, mesures, dimensions et helpers SQL.
- `pulsar_cube/cube/model/views/` : vues publiques exposees a l'agent.

Les vues publiques Cube constituent le meilleur contrat fonctionnel pour concevoir l'equivalent Snowflake :

- `orders_overview`
- `payments_overview`
- `catalog_sales`
- `reviews_overview`
- `category_satisfaction`
- `customer_cohorts`
- `customer_revenue_segments`
- `seller_delivery_performance`
- `top_customer_state_categories`

Ces vues ont ete concues pour eviter que l'agent n'invente des joins ou du SQL libre. Les questions complexes sont traitees par des helpers gouvernes, pas par une generation ad hoc.

### Evaluation existante

Le protocole actuel est deja bien separe :

- `docs/evaluation/QUESTION_CATALOG.md` decrit les questions de reference de maniere neutre, independamment de Cube.
- `docs/evaluation/pulsar_cube/PULSAR_CUBE_QUESTION_EVALUATION.md` mappe ces questions vers la surface Cube.
- `docs/evaluation/pulsar_cube/PULSAR_CUBE_COST_ESTIMATION.md` estime les couts de la solution Pulsar/Cube.

Cette separation doit etre conservee pour Snowflake Intelligence.

## Conventions metier a conserver

Les points suivants sont critiques pour comparer les solutions de facon juste :

- `revenue` designe le chiffre d'affaires marchand issu de `ORDER_ITEMS.PRICE`, hors frais de port, sauf mention contraire.
- `collected value`, `paid value` ou `payment value` designent `ORDER_PAYMENTS.PAYMENT_VALUE`, incluant frais de port et ajustements.
- `customer_id` est order-scoped dans Olist.
- `customer_unique_id` identifie un client physique et doit etre utilise pour les analyses repeat customer.
- Les categories produit sont en portugais dans `PRODUCTS`.
- Les noms anglais de categorie viennent de `PRODUCT_CATEGORY_NAME_TRANSLATION`.
- Les questions operationnelles et de performance livraison doivent generalement filtrer `ORDERS.ORDER_STATUS = 'delivered'`, sauf si la question demande explicitement toutes les commandes.
- `delay_days > 0` signifie livraison en retard.
- Les reviews sont au grain commande, pas au grain ligne article.

## Direction Snowflake recommandee

La documentation Snowflake actuelle recommande les **Semantic Views** natives pour definir les semantiques metier cote Snowflake.

Les semantic views sont des objets de schema Snowflake, integres au RBAC, au catalogue et aux mecanismes de partage. Elles peuvent etre creees depuis une specification YAML avec `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`.

Pour ce POC, il faut donc viser une semantic view Snowflake native plutot qu'un ancien fichier semantic model YAML stocke sur stage, sauf contrainte de compatibilite specifique.

References Snowflake :

- [YAML specification for semantic views](https://docs.snowflake.com/user-guide/views-semantic/semantic-view-yaml-spec)
- [Overview of semantic views](https://docs.snowflake.com/user-guide/views-semantic/overview)
- [Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)
- [Cortex Analyst evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- [Cortex Analyst semantic model specification](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec)

## Travaux a realiser

### 1. Creer une zone semantique Snowflake

Creer un schema dedie, par exemple :

```sql
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.SEMANTIC;
```

Ce schema pourra contenir :

- les vues SQL helper ;
- la semantic view native ;
- les objets de test ou d'evaluation si necessaire.

### 2. Porter les helpers Cube en vues SQL Snowflake

Plusieurs cas d'evaluation ne doivent pas etre traites par de simples joins automatiques, car ils impliquent des problemes de grain, d'attribution ou de ranking.

Il faut materialiser ou definir en vues Snowflake l'equivalent des helpers Cube suivants :

| Besoin | Objet Cube actuel | Raison |
|---|---|---|
| Satisfaction par categorie | `helper_category_satisfaction` | Eviter le fan-out review x order items. |
| Cohortes client 90 jours | `helper_customer_cohorts` | Logique multi-etapes par `customer_unique_id`. |
| Repeat vs one-time revenue | `helper_customer_revenue_segments` | Segmentation client avant aggregation revenue. |
| Performance livraison vendeur | `helper_seller_delivery_performance` | Grain seller/order-item et convention de retard. |
| Top categories par etat client | `helper_top_customer_state_categories` | Ranking par partition avec `ROW_NUMBER`. |

Ces objets doivent etre gouvernes comme faisant partie du modele semantique, pas consideres comme des requetes d'evaluation ponctuelles.

### 3. Definir la semantic view Snowflake

Creer une specification YAML pour une semantic view Olist, par exemple :

```text
snowflake/semantic/olist_semantic_view.yaml
```

Elle devra definir :

- les logical tables ;
- les primary keys ;
- les dimensions ;
- les facts ;
- les metrics ;
- les derived metrics ;
- les relationships ;
- les filtres metier utiles ;
- les synonymes ;
- les descriptions ;
- les verified queries.

Les noms de concepts doivent etre proches des vues Cube actuelles afin de faciliter la comparaison, mais il n'est pas obligatoire de reproduire exactement l'architecture Cube.

### 4. Ajouter les metrics et dimensions indispensables

La semantic view doit permettre de couvrir au minimum toutes les questions du catalogue :

- comptage des commandes ;
- comptage des clients physiques ;
- methodes de paiement les plus utilisees ;
- score moyen des reviews ;
- valeur collectee ;
- revenue par categorie anglaise ;
- revenue mensuel 2017 ;
- part des paiements multi-installments ;
- nombre de commandes avec paiement multi-installments ;
- meilleurs vendeurs selon KPI clarifie ;
- revenue par vendeur et par etat ;
- satisfaction par categorie ;
- top categories par etat client ;
- cohortes 90 jours ;
- performance livraison par etat vendeur ;
- impact des livraisons tardives sur satisfaction ;
- part de revenue repeat vs one-time customers.

### 5. Integrer les verified queries

Le fichier `docs/evaluation/QUESTION_CATALOG.md` doit servir de base aux verified queries.

Chaque question importante devrait avoir :

- une question en langage naturel ;
- une requete SQL Snowflake attendue ;
- une description de l'hypothese metier ;
- un statut de verification ;
- si possible, un resultat attendu ou un ordre de grandeur.

Les verified queries ont deux usages distincts :

- guider Cortex Analyst / Snowflake Intelligence pendant la generation SQL ;
- servir de ground truth pour les evaluations Cortex Analyst.

Attention : dans les evaluations Cortex Analyst, une verified query selectionnee comme cas de test est temporairement retiree de la semantic view de test afin d'eviter qu'elle ne guide directement la generation. Cela permet de mesurer la capacite de generalisation.

### 6. Configurer les roles et droits

Le role actuel `CUBE_READER` donne acces aux tables pour Cube, mais il faudra probablement creer ou adapter un role dedie Snowflake Intelligence / Cortex Analyst.

Permissions a prevoir :

- `USAGE` sur warehouse, database et schemas ;
- `SELECT` sur les tables et vues source ;
- `SELECT` et `MONITOR` sur la semantic view ;
- privileges necessaires aux evaluations Cortex Analyst si elles sont utilisees ;
- database role `SNOWFLAKE.CORTEX_USER` selon la configuration du compte.

La documentation Snowflake indique que les evaluations Cortex Analyst executent des tasks avec un role primaire unique. Les privileges requis doivent donc etre portes par ce role primaire, pas seulement par des roles secondaires.

### 7. Rejouer l'evaluation qualite

Creer un document miroir de l'evaluation Cube :

```text
docs/evaluation/snowflake_intelligence/SNOWFLAKE_QUESTION_EVALUATION.md
```

Pour chaque question :

- indiquer si Snowflake Intelligence peut repondre ;
- relever la reponse finale ;
- relever ou reconstruire le SQL genere ;
- comparer au SQL attendu ;
- noter les erreurs de filtre, de grain, de mesure ou d'ambiguite ;
- attribuer un statut : perfect, acceptable, partial, fail.

La comparaison doit rester centree sur les memes criteres que Pulsar/Cube afin de garder une evaluation equitable.

### 8. Mesurer les couts

Creer un document miroir :

```text
docs/evaluation/snowflake_intelligence/SNOWFLAKE_COST_ESTIMATION.md
```

Les couts a separer :

- cout Snowflake Intelligence / Cortex Analyst ;
- cout warehouse des requetes SQL generees ;
- cout eventuel des evaluations Cortex Analyst ;
- cout de stockage additionnel si les helpers sont materialises ;
- cout d'infrastructure externe evite par rapport a Pulsar/Cube.

Pour Snowflake, le cout ne sera pas comparable ligne a ligne avec Pulsar/Cube :

- Pulsar/Cube a un cout infra applicatif H24 ou on-demand ;
- Snowflake Intelligence deplace une partie du cout dans Snowflake/Cortex ;
- les requetes SQL continuent a consommer du warehouse compute ;
- les caches et la taille du warehouse peuvent fortement influencer le resultat.

## Livrables proposes

Structure recommandee :

```text
snowflake/
  sql/
    create_semantic_schema.sql
    create_semantic_helper_views.sql
    create_semantic_view.sql
    grants.sql
  semantic/
    olist_semantic_view.yaml
  README.md

docs/evaluation/snowflake_intelligence/
  SNOWFLAKE_QUESTION_EVALUATION.md
  SNOWFLAKE_COST_ESTIMATION.md
```

## Risques et points d'attention

### Risque principal : erreurs de grain

Les questions avancees ne sont pas de simples aggregations. Les erreurs les plus probables sont :

- compter des lignes de paiement au lieu de commandes ;
- compter des `customer_id` au lieu de `customer_unique_id` ;
- dupliquer les reviews en joignant directement reviews et order items ;
- sommer du payment value au lieu du merchandise revenue ;
- oublier le filtre `delivered` quand il est requis ;
- appliquer le filtre `delivered` quand la question demande toute la base ;
- classer les top categories globalement au lieu de par etat.

### Ambiguites metier

Certaines questions doivent etre resolues explicitement ou clarifiees :

- "best sellers" : revenue, nombre de ventes, satisfaction, performance livraison ?
- "customers" : clients physiques ou lignes `CUSTOMERS` order-scoped ?
- "revenue" vs "collected value" ;
- livraison "late" stricte apres date promise ou seuil plus large.

La semantic view doit contenir assez de descriptions et synonymes pour guider le comportement attendu.

### Parite Cube vs Snowflake

L'objectif n'est pas de reproduire techniquement Cube, mais de reproduire la capacite analytique exposee par Cube.

La comparaison doit donc porter sur :

- qualite des reponses ;
- robustesse aux ambiguites ;
- exactitude SQL ;
- cout ;
- effort de modelisation ;
- maintenabilite ;
- gouvernance ;
- experience utilisateur.

## Plan de mise en oeuvre recommande

1. Creer le dossier `snowflake/` et les scripts SQL de base.
2. Creer les vues SQL helper equivalentes aux helpers Cube.
3. Ecrire une premiere semantic view couvrant les questions simples et medium.
4. Ajouter les objets avances : cohortes, rankings, segmentation, satisfaction par categorie.
5. Ajouter les verified queries issues du catalogue.
6. Valider manuellement les SQL attendus dans Snowflake.
7. Connecter Snowflake Intelligence a la semantic view.
8. Rejouer toutes les questions du catalogue.
9. Documenter les resultats qualite.
10. Extraire et documenter les couts.

## Conclusion

Le chantier Snowflake ne doit pas etre traite comme une simple conversion YAML du modele Cube.

Le point essentiel est de porter les choix semantiques qui ont rendu le POC Cube fiable : conventions metier, controle des grains, helpers analytiques et descriptions explicites. Une fois cette couche stabilisee dans Snowflake, Snowflake Intelligence pourra etre evalue sur les memes questions que Pulsar/Cube, avec une comparaison juste de la qualite des reponses et du cout d'exploitation.
