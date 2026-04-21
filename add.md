# add.md — 27.2 : Nettoyage Casper

## 🎯 Contexte
Nous sommes sur Debian, pas Ubuntu. Le script fait référence à "casper", ce qui est incorrect.

## 🛠 ACTIONS
1. Dans `launch.sh`, remplace la détection du mode Live :
   - Au lieu de chercher `/casper` ou `boot=casper`, cherche `/lib/live/mount/medium` ou le flag `boot=live` dans `/proc/cmdline`.
2. Assure-toi que la variable `IS_LIVE` (ou équivalent) est bien mise à `true` si ces éléments Debian sont présents.
3. Vérifie que le chemin vers les paquets de secours (si présents) pointe vers `/lib/live/mount/medium/live/`.
