#!/usr/bin/env python3
"""
mt5_patch_param.py
------------------
Modifie la valeur d'un paramètre dans des fichiers MT5 .set et/ou .chr (encodés UTF-16 LE).

Usage :
    python mt5_patch_param.py --param ShowInfoPanel --value false
    python mt5_patch_param.py --param ShowInfoPanel --value false --folder "C:/mon/dossier"
    python mt5_patch_param.py --param ShowInfoPanel --value false --ext set
    python mt5_patch_param.py --param ShowInfoPanel --value false --ext chr
    python mt5_patch_param.py --param ShowInfoPanel --value false --dry-run

Options :
    --param     Nom du paramètre à modifier (ex: ShowInfoPanel)
    --value     Nouvelle valeur à appliquer (ex: false)
    --folder    Dossier contenant les fichiers (défaut : dossier courant)
    --ext       Extension(s) à traiter : set, chr, ou both (défaut : both)
    --dry-run   Affiche les changements sans modifier les fichiers
    --help      Affiche cette aide

Comportement :
  - Fichiers .set  : remplace la première valeur dans  param=VALEUR||...
  - Fichiers .chr  : remplace la valeur simple dans    param=VALEUR
  - Traite récursivement les sous-dossiers si --folder est un dossier de profil
  - Crée une sauvegarde .bak pour chaque fichier modifié
"""

import argparse
import os
import re
import sys
import shutil


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_utf16(path):
    """Lit un fichier UTF-16 LE (avec ou sans BOM) et retourne le texte."""
    raw = open(path, "rb").read()
    # Détection BOM
    if raw[:2] == b"\xff\xfe":
        return raw[2:].decode("utf-16-le")
    elif raw[:2] == b"\xfe\xff":
        return raw[2:].decode("utf-16-be")
    else:
        # Essai UTF-16 LE sans BOM
        return raw.decode("utf-16-le")


def write_utf16(path, content):
    """Écrit le texte en UTF-16 LE avec BOM."""
    open(path, "wb").write(b"\xff\xfe" + content.encode("utf-16-le"))


def patch_set_line(line, param, new_value):
    """
    Dans un .set, une ligne ressemble à :
        ShowInfoPanel=true||false||0||true||N
    On remplace uniquement la première valeur (avant le premier ||).
    """
    # Regex : param=VALEUR(||...) ou param=VALEUR(fin de ligne)
    pattern = re.compile(
        r"^(" + re.escape(param) + r"=)([^||\r\n]+?)((?:\|\|.*)?(?:\r?\n|$))",
        re.MULTILINE
    )
    return pattern.sub(lambda m: m.group(1) + new_value + m.group(3), line)


def patch_chr_line(line, param, new_value):
    """
    Dans un .chr, une ligne ressemble à :
        ShowInfoPanel=true
    On remplace la valeur directement.
    """
    pattern = re.compile(
        r"^(" + re.escape(param) + r"=)([^\r\n]+)",
        re.MULTILINE
    )
    return pattern.sub(lambda m: m.group(1) + new_value, line)


def process_file(path, param, new_value, dry_run):
    """Traite un fichier .set ou .chr. Retourne True si modifié."""
    ext = os.path.splitext(path)[1].lower()

    try:
        content = read_utf16(path)
    except Exception as e:
        print(f"  [ERREUR lecture] {path} : {e}")
        return False

    if ext == ".set":
        new_content = patch_set_line(content, param, new_value)
    elif ext == ".chr":
        new_content = patch_chr_line(content, param, new_value)
    else:
        return False

    if new_content == content:
        print(f"  [inchangé]   {os.path.basename(path)}  (paramètre absent ou déjà à cette valeur)")
        return False

    # Affiche la ligne modifiée pour confirmation
    for old_l, new_l in zip(content.splitlines(), new_content.splitlines()):
        if old_l != new_l:
            print(f"  [modifié]    {os.path.basename(path)}")
            print(f"               avant  : {old_l.strip()}")
            print(f"               après  : {new_l.strip()}")
            break

    if not dry_run:
        # Sauvegarde .bak
        shutil.copy2(path, path + ".bak")
        write_utf16(path, new_content)

    return True


def collect_files(folder, extensions):
    """Retourne la liste de tous les fichiers avec les extensions demandées."""
    result = []
    for root, dirs, files in os.walk(folder):
        # Ignore les dossiers cachés
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in extensions:
                result.append(os.path.join(root, f))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Patch un paramètre dans des fichiers MT5 .set et/ou .chr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--param",   required=True,  help="Nom du paramètre (ex: ShowInfoPanel)")
    parser.add_argument("--value",   required=True,  help="Nouvelle valeur (ex: false)")
    parser.add_argument("--folder",  default=".",    help="Dossier à traiter (défaut: dossier courant)")
    parser.add_argument("--ext",     default="both",
                        choices=["set", "chr", "both"],
                        help="Extensions à traiter (défaut: both)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simule sans modifier les fichiers")
    args = parser.parse_args()

    # Extensions à traiter
    if args.ext == "both":
        extensions = {".set", ".chr"}
    elif args.ext == "set":
        extensions = {".set"}
    else:
        extensions = {".chr"}

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        print(f"Erreur : le dossier '{folder}' n'existe pas.")
        sys.exit(1)

    files = collect_files(folder, extensions)
    if not files:
        print(f"Aucun fichier {extensions} trouvé dans : {folder}")
        sys.exit(0)

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Paramètre : {args.param}  →  {args.value}")
    print(f"Dossier   : {folder}")
    print(f"Fichiers  : {len(files)} trouvé(s)\n")
    print("-" * 60)

    modified = 0
    for path in files:
        if process_file(path, args.param, args.value, args.dry_run):
            modified += 1

    print("-" * 60)
    if args.dry_run:
        print(f"\n[DRY-RUN] {modified}/{len(files)} fichier(s) seraient modifiés. Aucun changement appliqué.")
    else:
        print(f"\n{modified}/{len(files)} fichier(s) modifié(s). Sauvegardes .bak créées.")


if __name__ == "__main__":
    main()
