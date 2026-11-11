# Voix off

Générateur de voix off en français pour mes vidéos : on écrit un texte, on obtient un **MP3** (et un WAV) prêt pour le montage, plus un fichier de **sous-titres SRT** synchronisé.

Synthèse vocale locale et gratuite avec [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (voix française `ff_siwis`) : pas de compte ni de clé API.

## Installation

```bash
./installer.sh
```

## Utilisation

1. Écrire le script dans `textes/ma_video.txt`.
2. Lancer :
   ```bash
   python3 voixoff.py textes/ma_video.txt
   ```
3. Récupérer `sorties/ma_video.mp3`, `sorties/ma_video.wav` et `sorties/ma_video.srt`.

Options : `--vitesse 1.1` (plus rapide), `--vitesse 0.9` (plus lent), `--sortie dossier/`.

## Syntaxe du texte

| Écriture | Effet |
|---|---|
| ligne vide | petite pause entre deux paragraphes |
| `[pause 2]` | pause de 2 secondes |
| `[vitesse 1.2]` | change la vitesse à partir de cet endroit |
| `# ...` | commentaire, non lu |

Exemple complet : `textes/exemple.txt`.
