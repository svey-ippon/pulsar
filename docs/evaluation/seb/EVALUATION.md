# Q1 - How many orders are in the database ?

```sql
select count(*) from fct_orders;
```

-> 99 441

## Pulsar
- OK
- Utilise la certified metric `order_count` → `COUNT(DISTINCT fo.ORDER_ID)` (distinct sert à rien sur cette table mais pas un drame)

# Q2 - How many customers are based in São Paulo state?
(Sao Paulo zip_code_prefix = SP)

- customer_zip_code_prefix est porté par la commande, pas par le customer (localisation au moment de la commande)
- jointure de la dim_geography nécessaire pour remonter au state
- state est un code alpha à deux char standard, mais pas le vrai nom du state (à déduire de la knowledge du modèle)
- quelques geolocations incomplètes (pas de state associé au zip_prefix) -> limitation de la requête


```sql
select
    count(distinct customer_unique_id)
from fct_orders fo
left join dim_geography dm
    on fo.customer_zip_code_prefix = dm.zip_code_prefix
where dm.state = 'SP';
```

-> 40 287

## Pulsar
- logique ok, description exacte des limites
- n'explicite pas l'utilisation de sa connaissance pour Sao Paulo = SP, fait la requête juste au premier coup -> il connait le dataset olist ...


# Q3 - What are the 5 most-used payment methods?

-- ambiguité: most used
-- critère nombre d'utilisation ou montant payé
-- le plus intuitif est par nombre d'utilisation, une levé de doute ou explicitation est nécessaire

-- ambiguité: si nombre d'utilisation, plusieurs méthode de paiements par commande
-- Une méthode utilisée x fois sur la même commande compte pour 1 ou pour X
-- pas de préférence, mais il faut au mieux lever l'ambiguité avant, au pire bien expliciter le choix


```sql
-- version nombre d'utilisation, par paiement
select
    payment_type,
    count(*) as cnt,
from fct_order_payments
group by payment_type
order by cnt desc 
limit 5;
```
