Pulsar — Cahier des charges V1

1. Contexte

Pulsar est une plateforme interne visant à remplacer certaines fonctionnalités de Snowflake Intelligence.

Objectif : permettre à un utilisateur métier d’interroger des données Snowflake en langage naturel via une interface conversationnelle simple.

Contraintes :

* Snowflake reste l’unique moteur d’exécution des requêtes.
* Couche sémantique indépendante basée sur Cube.
* Pas de RAG documentaire.
* Pas d’agents avec actions.
* Lecture seule.
* Multi-domaines.

Dataset initial : Olist Brazilian E-commerce.

⸻

2. Objectifs V1

Fonctionnalités incluses :

* Interface conversationnelle simple
* Question utilisateur en langage naturel
* Traduction NL → requête Cube
* Exécution indirecte sur Snowflake
* Explication des résultats
* Affichage SQL généré
* Affichage résultats tabulaires
* Feedback utilisateur
* Journalisation

Exclus :

* Actions métier
* Alertes
* Scheduling
* Partage
* RAG
* Modification de données
* Mémoire conversationnelle avancée
* Graphiques

⸻

3. Architecture cible

Utilisateur
    ↓
Frontend Chat
    ↓
API Backend (FastAPI)
    ↓
LLM Orchestrator
    ↓
Semantic Layer (Cube)
    ↓
Snowflake

Flux :

1. L’utilisateur pose une question.
2. Le backend récupère le contexte sémantique Cube.
3. Le LLM produit une requête structurée.
4. Validation.
5. Appel Cube.
6. Cube génère SQL.
7. Snowflake exécute.
8. Retour résultat.
9. Le LLM explique.

⸻

4. Composants

Frontend

Technologie cible :

* NextJS
* React

Fonctionnalités :

* chat simple
* historique local
* affichage réponse
* tableau résultats
* SQL généré
* bouton feedback

⸻

Backend

Technologie :

* Python
* FastAPI

Responsabilités :

* authentification
* orchestration
* appels LLM
* appels Cube
* audit
* validation

⸻

Cube Semantic Layer

Source : Snowflake BRAZILIAN_ECOMMERCE

Structure cible :

Fact tables :

* Orders
* OrderItems
* Payments
* Reviews

Dimensions :

* Customers
* Sellers
* Products
* Geography

Mesures :

* Revenue
* Order Count
* Average Basket
* Delivery Delay
* Average Review Score

Synonymes :

Revenue:

* CA
* sales
* turnover
* chiffre d’affaires

⸻

5. Sécurité

Interdictions :

* INSERT
* UPDATE
* DELETE
* MERGE
* DROP
* CREATE

Lecture seule.

Rôle Snowflake dédié :

PULSAR_READ_ROLE

Interdiction ACCOUNTADMIN.

⸻

6. Observabilité

Logs :

* question utilisateur
* requête Cube
* SQL généré
* durée
* coût
* erreurs

Métriques :

* temps réponse
* coût Snowflake
* taux erreur
* taux feedback négatif

⸻

7. Jeu de données

Database:

BRAZILIAN_ECOMMERCE

Schema:

RAW

Source : Olist

Tables :

* customers
* sellers
* products
* geolocation
* orders
* order_items
* order_payments
* order_reviews

⸻

8. Questions de référence

Questions simples :

* Quel est le chiffre d’affaires mensuel ?
* Quels états génèrent le plus de revenus ?
* Quels produits sont les plus vendus ?
* Quel est le panier moyen ?
* Quelle est la note moyenne ?

Questions complexes :

* Quels vendeurs ont une mauvaise satisfaction malgré un CA élevé ?
* Quel est l’impact du délai de livraison sur les reviews ?

⸻

9. Roadmap

V1

* Cube connecté
* semantic layer
* backend
* chat
* NL → Cube
* résultats

V2

* suggestion automatique de graphiques
* mémoire conversationnelle légère
* clarification automatique

V3

* agents
* alertes
* automatisation
