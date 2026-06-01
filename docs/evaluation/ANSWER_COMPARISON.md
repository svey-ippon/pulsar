# Answer Comparison

# S1 | Simple | How many orders are in the database?

cube-core: ok
snow-int: ok

pour les deux, la précision "across all order statuses" est donné

# S2 | Simple | How many customers are based in São Paulo state?

cube-core: ok
snow-int: ok

pour les deux, la précision "counted using customer_unique_id to reflect physical customers rather than order-scoped identities" est donnée


# S3 | Simple | What are the 5 most-used payment methods?

cube-core: ok
snow-int: ok

cube-core: précise le critère de ranking et une alternative "rank by total payment value instead of transaction count" 
snow-int: précise le critère de ranking, mais pas d'alternative

C'est dû au prompt, plus strict point de vue "limits and implicits" côté cube-core


# S4 | Simple | What is the average review score across all reviews?

cube-core: ok
snow-int: ok


# S5 | Simple | What is the total value collected across all orders?

cube-core: ok
snow-int: ok

# M1 | Medium | What are the top 10 product categories by total revenue? Show English category names.

cube-core: ok - "All order statuses are included (delivered, canceled, etc.)"
snow-int: ok - "total delivered merchandise revenue"

Filtrage différents sur les status order. Dans les deux cas explicité



# M2 | Medium | Show monthly revenue for 2017.

cube-core: ok - "All order statuses are included (delivered, canceled, etc.)"
snow-int: ok - "total delivered merchandise revenue"

Filtrage différents sur les status order. Dans les deux cas explicité, comme la question précédente

...
