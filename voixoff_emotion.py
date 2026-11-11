#!/usr/bin/env python3
"""Voix off expressive (avec émotions) via ElevenLabs v3.

Usage :
    python3 voixoff_emotion.py textes/ma_video.txt
    python3 voixoff_emotion.py textes/ma_video.txt --voix Charlotte
    python3 voixoff_emotion.py --liste-voix

Émotions : écrire des balises entre crochets directement dans le texte, en anglais
(c'est ce que le modèle comprend le mieux), par exemple :
    [excited] C'est incroyable !
    [whispers] Je vais vous confier un secret...
    [sad] Malheureusement, ça n'a pas marché.
    [laughs] [sarcastic] [curious] [angry] [sighs] [dramatic] [calm] [cheerful]
Quelques raccourcis français sont acceptés et traduits automatiquement :
    [joyeux] [excité] [triste] [chuchote] [rire] [soupir] [colère] [calme]
    [surpris] [curieux] [sarcastique] [dramatique] [peur] [enthousiaste]

Autres balises :
    [pause 2]   pause de 2 secondes
    # ...       ligne de commentaire (non lue)

Sorties : sorties/<nom>.mp3 et sorties/<nom>.srt (sous-titres).
La clé API est lue dans ELEVENLABS_API_KEY (ou injectée par le proxy de l'environnement cloud).
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io"
RACINE = Path(__file__).resolve().parent
MODELE = "eleven_v3"
LIMITE = 2800  # le modèle v3 accepte ~3000 caractères par requête

FR_EN = {
    "joyeux": "cheerful", "joyeuse": "cheerful", "heureux": "happy", "heureuse": "happy",
    "excité": "excited", "excitée": "excited", "enthousiaste": "enthusiastic",
    "triste": "sad", "chuchote": "whispers", "chuchoté": "whispers",
    "rire": "laughs", "rit": "laughs", "soupir": "sighs", "soupire": "sighs",
    "colère": "angry", "énervé": "angry", "calme": "calm", "doux": "softly",
    "surpris": "surprised", "surprise": "surprised", "curieux": "curious",
    "sarcastique": "sarcastic", "dramatique": "dramatic", "peur": "scared",
    "inquiet": "nervous", "mystérieux": "mysterious", "crie": "shouts",
}


def cle():
    return os.environ.get("ELEVENLABS_API_KEY", "proxy-injected")


def requete(chemin, corps=None):
    req = urllib.request.Request(
        API + chemin,
        data=json.dumps(corps).encode() if corps is not None else None,
        headers={"xi-api-key": cle(), "Content-Type": "application/json"},
        method="POST" if corps is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Erreur ElevenLabs {e.code} : {e.read().decode(errors='replace')}")


def voix_disponibles():
    return requete("/v1/voices")["voices"]


def trouver_voix(nom):
    if re.fullmatch(r"[A-Za-z0-9]{20}", nom):
        return nom
    for v in voix_disponibles():
        if v["name"].lower().startswith(nom.lower()):
            return v["voice_id"]
    sys.exit(f"Voix « {nom} » introuvable. Voir --liste-voix.")


def preparer(texte):
    """Retire les commentaires, traduit les balises françaises, découpe en blocs."""
    lignes = [l for l in texte.splitlines() if not l.lstrip().startswith("#")]
    texte = "\n".join(lignes).strip()

    def balise(m):
        mot = m.group(1).strip()
        p = re.fullmatch(r"pause\s+([\d.,]+)\s*s?", mot, re.I)
        if p:
            return f'<break time="{float(p.group(1).replace(",", ".")):.1f}s" />'
        return f"[{FR_EN.get(mot.lower(), mot)}]"

    texte = re.sub(r"\[([^\]]+)\]", balise, texte)
    # v3 ne gère pas <break> : on le remplace par des points de suspension proportionnels.
    texte = re.sub(r'<break time="([\d.]+)s" />',
                   lambda m: " " + "… " * max(1, round(float(m.group(1)))), texte)

    blocs, courant = [], ""
    for para in re.split(r"\n\s*\n", texte):
        para = " ".join(para.split())
        if courant and len(courant) + len(para) + 2 > LIMITE:
            blocs.append(courant)
            courant = ""
        courant = f"{courant}\n\n{para}".strip()
    if courant:
        blocs.append(courant)
    return blocs


def horodatage(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def sous_titres(caracteres, debuts, fins):
    """Regroupe l'alignement caractère par caractère en phrases (balises [..] retirées)."""
    segments, phrase, debut, dans_balise = [], "", None, False
    for c, a, b in zip(caracteres, debuts, fins):
        if c == "[":
            dans_balise = True
            continue
        if dans_balise:
            dans_balise = c != "]"
            continue
        if debut is None and c.strip():
            debut = a
        phrase += c
        if c in ".!?…" and len(phrase.strip()) > 1:
            segments.append((debut, b, " ".join(phrase.split())))
            phrase, debut = "", None
    if phrase.strip() and debut is not None:
        segments.append((debut, fins[-1], " ".join(phrase.split())))
    return [s for s in segments if re.search(r"\w", s[2])]


def main():
    p = argparse.ArgumentParser(description="Voix off expressive avec ElevenLabs.")
    p.add_argument("texte", type=Path, nargs="?")
    p.add_argument("--voix", default="Charlotte", help="nom ou identifiant de la voix")
    p.add_argument("--stabilite", type=float, default=0.0,
                   help="0.0 = créatif/très expressif, 0.5 = naturel, 1.0 = robuste/neutre")
    p.add_argument("--sortie", type=Path, default=RACINE / "sorties")
    p.add_argument("--liste-voix", action="store_true", help="affiche les voix disponibles")
    args = p.parse_args()

    if args.liste_voix:
        for v in voix_disponibles():
            l = v.get("labels", {})
            print(f"{v['name']:<28} {l.get('gender', ''):<8} {l.get('accent', ''):<14} "
                  f"{l.get('description', l.get('descriptive', ''))}  ({v['voice_id']})")
        return
    if not args.texte:
        p.error("indiquez un fichier texte")

    voice_id = trouver_voix(args.voix)
    blocs = preparer(args.texte.read_text(encoding="utf-8"))
    audio, srt, decalage = b"", [], 0.0

    for i, bloc in enumerate(blocs, 1):
        print(f"Bloc {i}/{len(blocs)} ({len(bloc)} caractères)…")
        r = requete(f"/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192", {
            "text": bloc,
            "model_id": MODELE,
            "language_code": "fr",
            "voice_settings": {"stability": args.stabilite},
        })
        audio += base64.b64decode(r["audio_base64"])
        al = r.get("alignment") or {}
        if al.get("characters"):
            for a, b, t in sous_titres(al["characters"],
                                       al["character_start_times_seconds"],
                                       al["character_end_times_seconds"]):
                srt.append((a + decalage, b + decalage, t))
            decalage += al["character_end_times_seconds"][-1]

    args.sortie.mkdir(parents=True, exist_ok=True)
    nom = args.texte.stem
    mp3 = args.sortie / f"{nom}.mp3"
    mp3.write_bytes(audio)
    (args.sortie / f"{nom}.srt").write_text(
        "\n".join(f"{i}\n{horodatage(a)} --> {horodatage(b)}\n{t}\n"
                  for i, (a, b, t) in enumerate(srt, 1)), encoding="utf-8")
    print(f"Durée ≈ {decalage:.1f} s → {mp3} et {nom}.srt")


if __name__ == "__main__":
    main()
