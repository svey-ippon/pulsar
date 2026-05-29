# Questions d'évaluation — Agent SQL sur le dataset Olist

Liste de ~20 questions de niveau moyen à complexe pour tester un agent capable d'interroger un data warehouse. Chaque question force une ou plusieurs techniques SQL au-delà de la simple agrégation/filtrage. La question et la technique visée sont séparées pour faciliter le scoring.

## Fenêtrage & classements

**1.** Quels sont les 3 produits générant le plus de chiffre d'affaires dans chaque catégorie ?
*Technique visée : partition + RANK*

**2.** Évolution mensuelle du CA avec le taux de croissance vs le mois précédent.
*Technique visée : LAG / variation période sur période*

**3.** Construis un Pareto des catégories : part dans le CA total et part cumulée.
*Technique visée : running total + ratio*

**4.** Pour chaque état (`state`), quel vendeur détient la plus grosse part du CA local ?
*Technique visée : rang par partition + part relative*

## Cohortes, rétention & récurrence

**5.** Pour les clients acquis chaque mois, quelle proportion repasse une commande dans les 3 et 6 mois suivants ?
*Technique visée : cohortes — dédupliquer sur `customer_unique_id`, pas `customer_id`*

**6.** Quel est le taux de clients récurrents (plus d'une commande) par état ?
*Technique visée : comptage par client dédupliqué + agrégation conditionnelle*

**7.** Quelle part du CA total provient des 20 % de clients les plus dépensiers ?
*Technique visée : déciles / NTILE + concentration*

**8.** Clients « à risque » : dernière commande ancienne combinée à une note moyenne basse.
*Technique visée : logique type RFM (récence + score combiné)*

## Logistique & délais

**9.** Délai moyen achat → livraison par état, et écart moyen vs la date estimée.
*Technique visée : différences de dates sur plusieurs jalons*

**10.** Le délai de livraison moyen s'améliore-t-il dans le temps ?
*Technique visée : série temporelle sur une métrique dérivée*

**11.** Délai entre achat et approbation du paiement selon le type de paiement.
*Technique visée : différence de dates + jointure orders/payments*

**12.** Commandes multi-vendeurs : combien impliquent plusieurs vendeurs, et est-ce que ça allonge le délai ?
*Technique visée : HAVING COUNT DISTINCT seller > 1*

## Corrélations & relations

**13.** Y a-t-il un lien entre retard de livraison et note de review ? Compare la distribution des notes pour les commandes livrées en retard vs à l'heure.
*Technique visée : bucketisation + jointure orders/reviews*

**14.** Effet du nombre de mensualités (`installments`) sur la valeur du paiement et sur le taux de reviews négatives.
*Technique visée : groupement par tranche + agrégation conditionnelle*

**15.** Distance vendeur → client (via `geolocation`) et son impact sur les frais de port et les délais.
*Technique visée : jointure géo + calcul de distance type haversine*

**16.** Délai entre livraison et soumission de la review (« time-to-review ») selon la note donnée.
*Technique visée : différence de dates + groupement par note*

## Distributions & segmentation

**17.** Panier moyen et nombre d'articles par commande : médiane et p90, pas seulement la moyenne.
*Technique visée : percentiles (PERCENTILE_CONT / approx)*

**18.** Catégories avec la meilleure et la pire satisfaction, en pondérant la note moyenne par le volume de commandes.
*Technique visée : moyenne pondérée + tri*

**19.** Saisonnalité : existe-t-il des pics de commandes par jour de semaine et par mois ?
*Technique visée : extraction de composantes de date + agrégation*

**20.** Top vendeurs par CA, avec leur note moyenne et leur part dans le CA total — un vendeur à fort volume est-il aussi bien noté ?
*Technique visée : plusieurs métriques croisées + part relative*

---

## Pièges utiles pour tester la robustesse

- **Déduplication** `customer_unique_id` vs `customer_id` (Q5–Q7).
- **Jonctions à plusieurs jalons de dates** : achat, approbation, livraison, estimation (Q9–Q11).
- **Distance géographique** qui demande un vrai calcul plutôt qu'une simple jointure (Q15).
