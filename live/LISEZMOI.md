# Elphara Fit Live

Lit Wii Fit Plus dans Dolphin et envoie les valeurs en direct à l'appli Elphara Fit (onglet Jeux → En direct) et à l'overlay OBS.

## Installation (une seule fois)

1. Installe Python 3 depuis python.org (coche « Add Python to PATH »).
2. Dans un terminal : `pip install dolphin-memory-engine`
3. Télécharge ce dossier `live` (elphara_live.py).

## Tester sans Dolphin

```
python elphara_live.py --demo
```

Le programme affiche ton code à 6 caractères. Tape-le dans l'appli : des fausses valeurs doivent bouger.

## Avec Dolphin

1. Lance Dolphin puis Wii Fit Plus.
2. `python elphara_live.py --watch`
3. Règle les adresses mémoire dans `elphara_live.json` (créé au premier lancement).

Chaque valeur : `nom`, `libelle`, `adresse` (ex. `"0x80ABCDEF"`), `type` (`u8`, `u16`, `u32`, `s8`, `s16`, `s32`, `float`), `actif`.
Options : `unite`, `plage` ([min, max] pour cop_x / cop_y), `facteur` (multiplie la valeur), `pointeur` (liste de décalages si l'adresse bouge), `noms` (traduit un numéro en texte, ex. `{"3": "Slalom"}`).

Noms spéciaux reconnus par l'appli : `cop_x` et `cop_y` (centre de gravité, affiché en cible), `poids`, `activite` (titre affiché en grand).

## Overlay OBS

Source « Navigateur » dans OBS, adresse : `https://elpharaa.github.io/Wii-fit-app-Elphara/overlay.html?c=TONCODE`, largeur 600, hauteur 250.
