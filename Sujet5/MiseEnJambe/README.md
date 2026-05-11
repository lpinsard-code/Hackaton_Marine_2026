## QUESTIONS

--- 
### 📌 QUESTIONS POUR LA MISE EN JAMBE : DÉTECTION DE NAVIRES SUR IMAGES SATELLITES

#### **🔹 Objectif**
Comprendre les bases de la détection d'objets (navires) sur images satellites.
Utiliser les fichiers :
- `images_metadata_small.csv` (20 images avec métadonnées)
- `annotations_small.json` (annotations au format COCO)
- Images satellites (à télécharger depuis les sources citées)

--- 

#### **📊 Partie 1 : Exploration des Métadonnées**
1. **Structure des métadonnées**
   - Quels sont les champs présents dans `images_metadata_small.csv` ?
   - Combien d'images contiennent plus de 1 navire ?

2. **Analyse des zones géographiques**
   - Quelles sont les **3 zones les plus représentées** dans le jeu de données ?
   - Combien d'images proviennent de zones à risque élevées (ex: Détroit de Malacca, Golfe Persique) ?

3. **Résolution et qualité des images**
   - Quelle est la **résolution la plus fréquente** dans le jeu de données ?
   - Quelle est la **couverture nuageuse moyenne** ?

--- 

#### **🔍 Partie 2 : Analyse des Annotations**
4. **Structure des annotations COCO**
   - Combien de catégories de navires sont définies dans `annotations_small.json` ?
   - Combien d'annotations (bounding boxes) sont présentes au total ?

5. **Répartition des types de navires**
   - Quel est le **type de navire le plus fréquent** dans les annotations ?
   - Combien de navires militaires (Frégate, Destroyer, Porte-avions) sont annotés ?

6. **Taille des bounding boxes**
   - Calculez la **taille moyenne** (en % de l'image) des bounding boxes.
   - Quel type de navire a les **plus grandes bounding boxes** en moyenne ?

--- 

#### **🖼️ Partie 3 : Visualisation et Détection Simple**
7. **Affichage d'une image et de ses annotations**
   - Chargez une image (ex: `satellite_000.jpg`) et affichez-la avec `matplotlib` ou `PIL`.
   - Dessinez les **bounding boxes** des annotations sur l'image (utilisez `cv2.rectangle` ou `matplotlib.patches.Rectangle`).
   - Affichez le **type de navire** pour chaque bounding box.

8. **Détection manuelle**
   - Pour 5 images, essayez de **compter manuellement** le nombre de navires visibles.
   - Comparez avec le nombre de navires annotés (`num_ships`). Y a-t-il des écarts ?

--- 

#### **💡 Partie 4 : Questions Ouvertes**
9. **Limites des annotations**
   - Quels sont les **problèmes potentiels** avec les annotations manuelles (ex: erreurs de localisation, classification incorrecte) ?
   - Comment pourrait-on **améliorer la qualité** des annotations ?

10. **Améliorations pour la détection automatique**
    - Quels **champs supplémentaires** pourraient être utiles dans les métadonnées pour faciliter la détection automatique ?
    - Comment pourrait-on **automatiser** la génération des bounding boxes ?

--- 

#### **📌 Consignes pour les Réponses**
- **Format des réponses** : Utilisez `pandas` pour analyser les métadonnées et `json` pour les annotations.
- **Exemple de réponse** :
  ```python
  import pandas as pd
  images = pd.read_csv("images_metadata_small.csv")
  print(f"Nombre d'images avec >1 navire : {len(images[images['num_ships'] > 1])}")
  ```
- **Livrable** : Un fichier `reponses_mise_en_jambe_detection_navires.py`.

