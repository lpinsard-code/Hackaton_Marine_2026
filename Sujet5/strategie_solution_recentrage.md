# Sujet 5 - Contexte, stratégie et état du projet

## Résumé en une phrase

Nous ne cherchons pas à refaire toute la computer vision : nous exploitons des résultats de détection déjà fournis pour construire une couche de renseignement maritime, avec scoring, visualisation géographique et priorisation des navires militaires détectés dans des zones sensibles.

## Contexte du hackathon

Le sujet 5 s'appelle **Chasse aux navires de guerre**.

L'objectif général est de montrer comment des images satellites et des données ouvertes peuvent aider à détecter, classifier et prioriser des navires visibles en mer ou dans des ports.

La Marine Nationale n'attend pas une solution parfaite. Elle attend une démarche crédible, rapide, documentée et exploitable :

- quelles données avons-nous ;
- que peut-on en tirer ;
- quelles limites devons-nous reconnaître ;
- comment transformer une sortie technique en information utile pour un analyste.

Le point important est donc le passage de la donnée brute au renseignement exploitable.

## Clarification importante sur les données

Au départ, nous pensions devoir récupérer des images satellites réelles et refaire une détection d'image complète.

Les nouvelles informations changent ce cadrage.

Les dossiers fournis dans `Sujet5` sont déjà une base de travail structurée avec computer vision réalisée ou simulée :

- `Sujet5/MiseEnJambe`
- `Sujet5/Généralisation`

Ces dossiers ne sont pas seulement des exemples. Ils contiennent déjà les éléments nécessaires pour construire un MVP métier.

## Données disponibles dans `MiseEnJambe`

Le dossier `Sujet5/MiseEnJambe` sert à comprendre les bases.

Il contient :

- `images_metadata_small.csv` : 20 images avec métadonnées ;
- `annotations_small.json` : annotations au format COCO ;
- un README avec des questions guidées.

Ce dataset permet surtout de comprendre :

- la structure des métadonnées ;
- le format COCO ;
- les catégories de navires ;
- la logique des bounding boxes ;
- les limites des annotations.

Il sert d'étape pédagogique, pas de base finale pour la stratégie.

## Données disponibles dans `Généralisation`

Le dossier `Sujet5/Généralisation` est la base principale du projet.

Il contient :

- `images_metadata_large.csv` : 100 images ou zones observées, avec date, source, résolution, coordonnées, zone, niveau de risque et couverture nuageuse ;
- `annotations_large.json` : annotations COCO avec catégories de navires ;
- `detection_results.csv` : résultats de détection, une ligne par navire détecté ;
- `military_zones.csv` : zones militaires ou sensibles, avec coordonnées, niveau de risque et statut actif ;
- `README.md` : questions de généralisation, dont certaines vont plus loin que ce qui est réaliste dans le temps disponible.

La donnée la plus importante est `detection_results.csv`, car elle représente déjà une sortie de computer vision exploitable.

## Problème des images

Les fichiers CSV contiennent des URLs d'images, mais elles pointent vers `example.com`.

Cela veut dire que nous ne pouvons pas ouvrir directement les images satellites associées.

Ce n'est pas bloquant pour le MVP, car nous avons déjà :

- les bounding boxes ;
- les catégories détectées ;
- le niveau de confiance ;
- l'information civil / militaire ;
- les zones ;
- les coordonnées ;
- les niveaux de risque.

Nous devons donc assumer clairement ceci :

> Les images ne sont pas accessibles directement, mais les résultats de computer vision sont déjà présents. Notre travail consiste à exploiter ces résultats.

## Rôle de Hugging Face

Le README global mentionne le dataset Hugging Face :

`DefendIntelligence/vessel-detection-labeled-patches`

Nous avons vérifié sa structure. Ce dataset est utile, mais il ne doit pas devenir le coeur du projet.

Il contient de vraies images satellites en patches et des labels de détection de bateaux. Il peut aider à :

- montrer à quoi ressemble une vraie donnée satellite annotée ;
- comprendre un format image + label YOLO ;
- illustrer une détection visuelle ;
- récupérer quelques exemples d'images réelles.

Mais il ne répond pas directement au sujet militaire, car les classes sont principalement :

- `boat`
- `background`
- `porte-conteneur`
- `inconnu`

Il ne permet donc pas de distinguer proprement frégate, destroyer, porte-avions ou navire militaire.

Conclusion :

> Hugging Face est une source secondaire pour illustrer la donnée image. La base métier reste `Sujet5/Généralisation`.

## Nouvelle problématique du projet

La question à traiter n'est plus :

> Peut-on entraîner rapidement un modèle parfait de détection de navires militaires ?

La vraie question devient :

> Comment transformer des résultats de computer vision déjà disponibles en outil de priorisation OSINT pour identifier les observations navales les plus sensibles ?

Cette formulation est plus réaliste, plus défendable et plus proche de ce que les données permettent vraiment.

## MVP visé

Le MVP doit prendre les fichiers fournis et produire une lecture opérationnelle.

Chaîne cible :

```text
métadonnées image
    + résultats de détection
    + zones militaires
    -> enrichissement géographique
    -> score de priorité
    -> carte et tableau de briefing
```

Le résultat attendu est un outil qui aide à répondre à ces questions :

- où sont les détections les plus sensibles ;
- quels navires militaires sont détectés ;
- quelles zones critiques concentrent le plus d'observations ;
- quelles détections doivent être vérifiées en priorité par un humain ;
- quelles limites empêchent une conclusion trop forte.

## Logique métier

Nous ne vendons pas une vérité automatique.

Nous proposons une aide au tri.

Un analyste humain ne doit pas lire toutes les lignes de détection une par une. Le système doit lui faire remonter les cas les plus intéressants :

- navire militaire ;
- zone critique ;
- forte confiance ;
- type stratégique ;
- proximité d'une zone militaire active.

Le projet doit donc être présenté comme une couche de priorisation au-dessus de la computer vision.

## Scoring retenu

Un score simple, transparent et défendable est préférable à un score complexe impossible à expliquer.

Règle actuelle :

- +40 si le navire est militaire ;
- +25 si la zone est `Critical` ;
- +15 si la zone est `High` ;
- +15 si la confiance est supérieure ou égale à 0.85 ;
- +8 si la confiance est entre 0.75 et 0.85 ;
- +20 si le type est stratégique : porte-avions, sous-marin, destroyer, croiseur ;
- +10 si la zone militaire la plus proche est active et à moins de 25 km.

Ce score sert à trier les observations. Il ne mesure pas une menace réelle.

## Travail géospatial

Les fichiers fournissent des coordonnées sous forme texte :

```text
latitude,longitude
```

Ces coordonnées permettent de construire une visualisation géographique.

Limite importante :

les détections n'ont pas de coordonnées GPS individuelles. Elles ont une bounding box dans l'image et une zone associée.

La carte localise donc les observations au niveau de la zone ou de l'image, pas au niveau exact du navire.

Cette limite doit être assumée :

> Notre carte est une carte de priorisation par zone, pas une carte tactique de position exacte.

## Fichiers produits à ce stade

### Notebooks de compréhension

- `Sujet5/MiseEnJambe/reponses_mise_en_jambe_detection_navires.ipynb`
- `Sujet5/Généralisation/reponses_generalisation_detection_navires.ipynb`

Ces notebooks répondent aux questions des README et expliquent la structure des données.

### Notebook Hugging Face

- `Sujet5/reponses_dataset_huggingface_vessel_patches.ipynb`

Ce notebook sert à comprendre la vraie donnée image Hugging Face, mais il reste secondaire.

### Notebook géospatial principal

- `Sujet5/Généralisation/analyse_geospatiale_priorisation_navires.ipynb`

Ce notebook est le plus important pour notre solution actuelle.

Il :

- lit les métadonnées ;
- lit les résultats de détection ;
- lit les zones militaires ;
- parse les coordonnées ;
- rattache les détections aux zones ;
- calcule une distance à la zone militaire la plus proche ;
- calcule un score de priorité ;
- génère des graphiques ;
- exporte des fichiers enrichis ;
- produit une carte HTML interactive.

### Exports générés

- `Sujet5/Généralisation/detections_enrichies_scoring.csv`
- `Sujet5/Généralisation/zones_resume_scoring.csv`
- `Sujet5/Généralisation/carte_priorisation_navires.html`

Ces fichiers sont directement utiles pour la présentation.

## Ce qu'il faut montrer au jury

Le message doit rester simple :

1. Nous avons compris que les résultats CV sont déjà disponibles.
2. Nous les avons transformés en outil d'aide à la décision.
3. Nous avons ajouté une couche géographique.
4. Nous avons créé un score transparent.
5. Nous savons expliquer les limites.

Le bon angle de présentation :

> Nous aidons l'analyste à prioriser les observations navales sensibles, au lieu de lui donner une liste brute de détections.

## Ce qu'il ne faut pas sur-vendre

Il ne faut pas dire :

- que nous avons entraîné un modèle complet de détection militaire ;
- que la carte donne la position exacte des navires ;
- que le score mesure une menace réelle ;
- que Hugging Face résout la classification militaire ;
- que les images originales du dataset fourni ont été vérifiées visuellement.

Il faut dire :

- que nous exploitons des sorties de computer vision ;
- que nous construisons une chaîne de priorisation ;
- que les résultats doivent être validés par un humain ;
- que la méthode est améliorable si les vraies images deviennent disponibles.

## Suite logique du projet

Priorité 1 : améliorer la carte et le briefing.

Priorité 2 : affiner le scoring avec des règles métier plus crédibles.

Priorité 3 : produire un tableau final des 10 observations les plus importantes.

Priorité 4 : utiliser quelques images Hugging Face uniquement pour illustrer la partie image satellite.

Priorité 5 : si le temps le permet, ajouter une dépendance comme `folium` ou `geopandas` pour une cartographie plus propre.

## Conclusion

Le projet est maintenant recadré.

La valeur n'est pas dans le fait de télécharger le plus gros dataset possible. La valeur est dans la transformation de sorties de computer vision en information exploitable pour la Marine Nationale.

Notre positionnement final :

> Une chaîne OSINT de priorisation des navires militaires détectés, combinant computer vision fournie, contexte géographique, score métier et visualisation cartographique.
