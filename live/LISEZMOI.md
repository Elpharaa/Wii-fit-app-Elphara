# Elphara Fit – connexion Dolphin

Ce programme relie Wii Fit Plus (sur Dolphin) à l'appli Elphara Fit.

## Installation (une seule fois)

1. Installe Python 3 depuis python.org (coche « Add Python to PATH »).
2. Mets `elphara_live.py` et `Lancer Elphara.bat` dans un même dossier (par ex. `Documents\ElpharaLive`).

## Utilisation

1. Double-clique sur **Lancer Elphara.bat**. Laisse la fenêtre ouverte.
2. La première fois, ouvre le lien affiché (ou tape le code à 8 caractères dans l'appli : Jeux → En direct).
3. Joue à Wii Fit Plus sur Dolphin. Chaque fois que le jeu enregistre (après un test de forme), tes résultats arrivent dans l'appli (Suivi → Wii Fit Plus).

Le programme trouve tout seul la sauvegarde de Dolphin. Si elle est ailleurs, indique le dossier utilisateur de Dolphin dans `elphara_live.json` (`"dossier_dolphin"`), ou lance `python elphara_live.py --save CHEMIN\FitPlus0.dat`.

Ne partage pas `elphara_live.json` : il contient la clé qui permet d'envoyer tes données.

## Direct pendant les parties (optionnel, avancé)

`pip install dolphin-memory-engine`, puis règle des adresses mémoire dans `elphara_live.json` (`valeurs`, avec `"actif": true`). Noms reconnus par l'appli : `cop_x`, `cop_y` (centre de gravité), `poids`, `score`, `activite`.

## Overlay OBS

Source « Navigateur » : `https://elpharaa.github.io/Wii-fit-app-Elphara/overlay.html?c=TONCODE` (600 × 250).
