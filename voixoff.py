#!/usr/bin/env python3
"""Génère une voix off (MP3 + WAV + sous-titres SRT) à partir d'un texte.

Usage :
    python3 voixoff.py textes/ma_video.txt
    python3 voixoff.py textes/ma_video.txt --vitesse 1.1 --sortie sorties/

Syntaxe du texte :
    - Une ligne vide = petite pause (0,6 s par défaut).
    - [pause 2] ou [pause 1.5s] = pause de la durée indiquée (en secondes).
    - [vitesse 1.2] = change la vitesse à partir de cet endroit.
    - Les lignes qui commencent par # sont des commentaires (non lus).
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

RACINE = Path(__file__).resolve().parent
MODELE = RACINE / "modeles" / "kokoro-v1.0.int8.onnx"
VOIX = RACINE / "modeles" / "voices-v1.0.bin"

PAUSE_PARAGRAPHE = 0.6
BALISE = re.compile(r"\[(pause|vitesse)\s+([\d.,]+)\s*s?\]", re.IGNORECASE)


def decouper(texte):
    """Transforme le texte en une liste d'éléments ('parole', str) / ('pause', s) / ('vitesse', x)."""
    elements = []
    lignes = [l for l in texte.splitlines() if not l.lstrip().startswith("#")]
    paragraphes = re.split(r"\n\s*\n", "\n".join(lignes))
    for i, para in enumerate(paragraphes):
        para = " ".join(para.split())
        if not para:
            continue
        if i > 0 and elements:
            elements.append(("pause", PAUSE_PARAGRAPHE))
        pos = 0
        for m in BALISE.finditer(para):
            ajouter_phrases(elements, para[pos:m.start()])
            elements.append((m.group(1).lower(), float(m.group(2).replace(",", "."))))
            pos = m.end()
        ajouter_phrases(elements, para[pos:])
    return elements


def ajouter_phrases(elements, morceau):
    # Une phrase par segment : meilleure prosodie et sous-titres plus fins.
    for phrase in re.split(r"(?<=[.!?…])\s+", morceau.strip()):
        if phrase.strip():
            elements.append(("parole", phrase.strip()))


def horodatage(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    p = argparse.ArgumentParser(description="Génère une voix off française.")
    p.add_argument("texte", type=Path, help="fichier texte du script")
    p.add_argument("--vitesse", type=float, default=1.0, help="vitesse de lecture (défaut 1.0)")
    p.add_argument("--voix", default="ff_siwis", help="voix Kokoro (défaut ff_siwis, française)")
    p.add_argument("--langue", default="fr-fr", help="langue (défaut fr-fr)")
    p.add_argument("--sortie", type=Path, default=RACINE / "sorties", help="dossier de sortie")
    args = p.parse_args()

    if not MODELE.exists() or not VOIX.exists():
        sys.exit("Modèles absents : lancez d'abord ./installer.sh")

    elements = decouper(args.texte.read_text(encoding="utf-8"))
    kokoro = Kokoro(str(MODELE), str(VOIX))
    sr = 24000
    vitesse = args.vitesse
    morceaux, srt, t = [], [], 0.0

    for genre, valeur in elements:
        if genre == "vitesse":
            vitesse = valeur
        elif genre == "pause":
            morceaux.append(np.zeros(int(valeur * sr), dtype=np.float32))
            t += valeur
        else:
            audio, sr = kokoro.create(valeur, voice=args.voix, speed=vitesse, lang=args.langue)
            duree = len(audio) / sr
            srt.append((t, t + duree, valeur))
            morceaux.append(audio.astype(np.float32))
            # Petit souffle naturel entre deux phrases.
            morceaux.append(np.zeros(int(0.25 * sr), dtype=np.float32))
            t += duree + 0.25
            print(f"  [{horodatage(t)}] {valeur}")

    son = np.concatenate(morceaux) if morceaux else np.zeros(1, dtype=np.float32)
    pic = np.max(np.abs(son))
    if pic > 0:
        son = son / pic * 0.89  # normalisation à environ -1 dBFS

    args.sortie.mkdir(parents=True, exist_ok=True)
    nom = args.texte.stem
    wav = args.sortie / f"{nom}.wav"
    mp3 = args.sortie / f"{nom}.mp3"
    sf.write(wav, son, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                    "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
    (args.sortie / f"{nom}.srt").write_text(
        "\n".join(f"{i}\n{horodatage(a)} --> {horodatage(b)}\n{txt}\n"
                  for i, (a, b, txt) in enumerate(srt, 1)),
        encoding="utf-8")

    print(f"\nDurée : {len(son) / sr:.1f} s")
    print(f"Fichiers : {mp3}, {wav}, {args.sortie / (nom + '.srt')}")


if __name__ == "__main__":
    main()
