#!/usr/bin/env python3
"""arkalabs-messenger — une boîte aux lettres JSON partagée entre agents IA.

Un seul fichier, bibliothèque standard seulement (Python 3.8+), identique sur
macOS, Windows et Linux. Voir README.md (humains) et AGENTS.md (agents).

Fichiers, dans le dossier partagé :
  boite.json            la boîte — source de vérité, exploitable par programme
  boite.manifest.json   les comptes des agents
  boite.md              vue lisible, régénérée à chaque écriture (ne pas éditer)
  pièces jointes        fichiers référencés par les messages

Commandes :
  init       crée une boîte vide, son manifeste et sa vue
  setup      mémorise le chemin de la boîte sur ce poste
  register   crée (ou met à jour) le compte d'un agent
  agents     liste les comptes : qui est qui, sur quelle machine, pour quoi faire
  deactivate désactive un compte (il n'est jamais supprimé)
  send       poste un message
  check      relève les messages « nouveau » adressés à un agent (pour les hooks)
  mark       fait avancer le statut d'un message reçu (nouveau → lu → traité)
  list       affiche les messages, filtrés au besoin
  watch      attend le prochain message adressé à un agent, puis rend la main
  migrate    importe une boîte Markdown existante

Codes de sortie : 0 succès ; 1 erreur d'usage ; 2 courrier présent (check
--wake) ; 3 rien reçu avant l'échéance (watch).
"""
import argparse
import contextlib
import datetime as dt
import json
import os
import platform
import re
import shutil
import sys
import time

VERSION = "0.1.0"
FORMAT = 1
STATUTS = ("nouveau", "lu", "traité")
CONFIG = os.path.join(os.path.expanduser("~"), ".arkalabs-messenger.json")
RE_NOM = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,31}$")


# --------------------------------------------------------------------------- #
# Fichiers
# --------------------------------------------------------------------------- #
def manifeste_de(boite):
    return os.path.splitext(boite)[0] + ".manifest.json"


def vue_de(boite):
    return os.path.splitext(boite)[0] + ".md"


def ecrire(chemin, texte):
    """Remplacement atomique : écrit à côté, puis remplace."""
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(texte)
    os.replace(tmp, chemin)


def en_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def lire_boite(boite):
    try:
        with open(boite, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"boîte introuvable : {boite} (crée-la avec `init`)")
    except ValueError:
        raise SystemExit(f"boîte illisible, JSON invalide : {boite}")
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise SystemExit(f"boîte non conforme (clé « messages » absente) : {boite}")
    return data


def enregistrer_boite(boite, data):
    ecrire(boite, en_json(data))
    ecrire(vue_de(boite), rendre_vue(data, boite))


@contextlib.contextmanager
def verrou(chemin, attente=20.0, perime=60.0):
    """Verrou par fichier `<chemin>.lock` (création exclusive), sûr sur un partage réseau."""
    lock = chemin + ".lock"
    debut = time.time()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > perime:
                    os.remove(lock)  # verrou abandonné par un processus mort
                    continue
            except OSError:
                continue
            if time.time() - debut > attente:
                raise SystemExit(f"verrouillé depuis plus de {attente:.0f} s : {lock}")
            time.sleep(0.2)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.remove(lock)


# --------------------------------------------------------------------------- #
# Vue Markdown, pour les humains
# --------------------------------------------------------------------------- #
def ligne_objet(m):
    return (f"Re : {m['re']} — " if m.get("re") else "") + m["objet"]


def lien(pj):
    return f"[{pj}]({pj})" if pj else "—"


def rendre_vue(data, boite):
    source = os.path.basename(boite)
    sortie = [
        "# Boîte aux lettres des agents — vue générée",
        "",
        f"> Vue lisible régénérée par `messenger.py` à chaque écriture. **Ne pas "
        f"éditer** : la source est `{source}`. Comptes : "
        f"`{os.path.basename(manifeste_de(boite))}`.",
        "",
        "## Messages",
        "",
    ]
    for m in reversed(data["messages"]):
        sortie.append(f"### {m['id']} · {ligne_objet(m)}")
        sortie.append(f"**De** {m['de']} → **À** {', '.join(m['a'])} · "
                      f"**Statut** {m['statut']} · **PJ** {lien(m.get('pj'))}")
        sortie.extend(m.get("corps", []))
        sortie.append("")
    return "\n".join(sortie)


# --------------------------------------------------------------------------- #
# Manifeste des comptes
# --------------------------------------------------------------------------- #
def lire_manifeste(boite):
    """Le manifeste, ou None s'il n'existe pas."""
    chemin = manifeste_de(boite)
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except ValueError:
        raise SystemExit(f"manifeste illisible, JSON invalide : {chemin}")


def ecrire_manifeste(boite, manifeste):
    ecrire(manifeste_de(boite), en_json(manifeste))


def manifeste_vide(boite):
    return {"version": FORMAT, "boite": os.path.basename(boite), "comptes": []}


def comptes_actifs(boite):
    """Noms des comptes actifs, ou None si la boîte n'a pas de manifeste."""
    m = lire_manifeste(boite)
    return None if m is None else {c["nom"] for c in m.get("comptes", []) if c.get("actif", True)}


# --------------------------------------------------------------------------- #
# Résolution de la boîte et de l'agent
# --------------------------------------------------------------------------- #
def config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def boite_de(args, obligatoire=True):
    boite = getattr(args, "box", None) or os.environ.get("MESSENGER_BOX") or config().get("box")
    if not boite:
        if obligatoire:
            raise SystemExit("boîte inconnue : passe --box, ou MESSENGER_BOX, ou `messenger.py setup --box <chemin>`")
        return None
    boite = os.path.expanduser(boite)
    if not boite.endswith(".json"):
        raise SystemExit(f"la boîte est un fichier .json ; pour une boîte Markdown, utilise `migrate` : {boite}")
    return boite


def agent_de(args):
    agent = getattr(args, "agent", None) or os.environ.get("MESSENGER_AGENT")
    if not agent:
        raise SystemExit("agent inconnu : passe --agent <nom>, ou MESSENGER_AGENT")
    if not RE_NOM.match(agent):
        raise SystemExit(f"nom d'agent invalide « {agent} » : minuscules, chiffres, . _ - (32 max)")
    return agent


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #
def maintenant():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def pour(data, agent, statut="nouveau"):
    return [m for m in data["messages"] if agent in m["a"] and (statut is None or m["statut"] == statut)]


def resume(m):
    return f"- {m['id']} · {ligne_objet(m)}  (de {m['de']} · PJ : {m.get('pj') or '—'})"


def nouvel_id(data, de):
    base = f"{dt.datetime.now().strftime('%Y%m%d-%H%M')}-{de}"
    ids, mid, n = {m["id"] for m in data["messages"]}, base, 2
    while mid in ids:
        mid, n = f"{base}-{n}", n + 1
    return mid


# --------------------------------------------------------------------------- #
# Commandes
# --------------------------------------------------------------------------- #
def cmd_init(args):
    boite = boite_de(args)
    if os.path.exists(boite):
        raise SystemExit(f"existe déjà, rien écrit : {boite}")
    os.makedirs(os.path.dirname(os.path.abspath(boite)), exist_ok=True)
    enregistrer_boite(boite, {"version": FORMAT, "messages": []})
    if not os.path.exists(manifeste_de(boite)):
        ecrire_manifeste(boite, manifeste_vide(boite))
    print(f"boîte créée     : {boite}")
    print(f"comptes         : {manifeste_de(boite)}")
    print(f"vue (lecture)   : {vue_de(boite)}")
    return 0


def cmd_setup(args):
    boite = os.path.abspath(boite_de(args))
    lire_boite(boite)
    conf = config()
    conf["box"] = boite
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)
    print(f"boîte mémorisée pour ce poste dans {CONFIG} : {boite}")
    return 0


def cmd_register(args):
    boite, nom = boite_de(args), agent_de(args)
    role = " ".join(args.role.split())
    if not role:
        raise SystemExit("rôle vide : dis en une ligne ce que fait cet agent")
    with verrou(manifeste_de(boite)):
        m = lire_manifeste(boite) or manifeste_vide(boite)
        comptes = m.setdefault("comptes", [])
        existant = next((c for c in comptes if c["nom"] == nom), None)
        if existant and not args.update:
            raise SystemExit(
                f"le compte « {nom} » existe déjà ({existant.get('hote')}, {existant.get('machine')}, "
                f"« {existant.get('role')} ») : choisis un autre nom, ou --update si c'est bien toi")
        avant = existant or {}
        compte = {
            "nom": nom,
            "hote": args.host,
            "modele": args.model or avant.get("modele"),
            "machine": args.machine or avant.get("machine") or platform.node(),
            "role": role,
            "humain": args.human or avant.get("humain"),
            "releve": args.wake or avant.get("releve"),
            "cree": avant.get("cree") or maintenant(),
            "actif": True,
        }
        compte = {k: v for k, v in compte.items() if v is not None}
        if existant:
            comptes[comptes.index(existant)] = compte
        else:
            comptes.append(compte)
        ecrire_manifeste(boite, m)
    print(f"compte {'mis à jour' if existant else 'créé'} : {nom} ({compte['hote']}, {compte['machine']})")
    return 0


def cmd_agents(args):
    boite = boite_de(args)
    m = lire_manifeste(boite)
    if m is None:
        print(f"pas de manifeste pour cette boîte ({manifeste_de(boite)}) : aucun compte")
        return 0
    if args.json:
        print(en_json(m), end="")
        return 0
    for c in m.get("comptes", []):
        if not c.get("actif", True) and not args.all:
            continue
        etat = "" if c.get("actif", True) else "  [désactivé]"
        print(f"{c['nom']:18} {c.get('hote', '?'):12} {c.get('machine', '?'):22} {c.get('role', '')}{etat}")
    return 0


def cmd_deactivate(args):
    boite, nom = boite_de(args), agent_de(args)
    with verrou(manifeste_de(boite)):
        m = lire_manifeste(boite)
        compte = next((c for c in (m or {}).get("comptes", []) if c["nom"] == nom), None)
        if not compte:
            raise SystemExit(f"compte introuvable : {nom}")
        compte["actif"] = False
        ecrire_manifeste(boite, m)
    print(f"compte désactivé : {nom} (conservé dans le manifeste, réactivable par register --update)")
    return 0


def cmd_send(args):
    boite, de = boite_de(args), agent_de(args)
    dest = list(dict.fromkeys(d.strip() for d in args.to.split(",") if d.strip()))
    for d in dest:
        if not RE_NOM.match(d):
            raise SystemExit(f"destinataire invalide « {d} »")
    corps = [l.rstrip() for l in (args.body or "").splitlines() if l.strip()]
    if len(corps) > 2:
        raise SystemExit("corps de plus de deux lignes : mets le détail dans une pièce jointe (--attach)")
    objet = " ".join(args.subject.split())
    if not objet:
        raise SystemExit("objet vide")
    actifs = comptes_actifs(boite)
    if actifs is None:
        sys.stderr.write("(boîte sans manifeste : destinataires non vérifiés — crée les comptes avec `register`)\n")
    else:
        if de not in actifs:
            raise SystemExit(f"« {de} » n'a pas de compte actif : `messenger.py register --agent {de} --host … --role …`")
        inconnus = [d for d in dest if d not in actifs]
        if inconnus:
            raise SystemExit(f"destinataire(s) sans compte actif : {', '.join(inconnus)} — "
                             f"comptes actifs : {', '.join(sorted(actifs))}")
    pj = None
    if args.attach:
        source = os.path.abspath(os.path.expanduser(args.attach))
        if not os.path.isfile(source):
            raise SystemExit(f"pièce jointe introuvable : {source}")
        pj = os.path.basename(source)
        cible = os.path.join(os.path.dirname(os.path.abspath(boite)), pj)
        if os.path.normcase(source) != os.path.normcase(cible):
            if os.path.exists(cible):
                raise SystemExit(f"un fichier « {pj} » existe déjà dans la boîte : renomme ta pièce jointe")
            shutil.copy2(source, cible)
    with verrou(boite):
        data = lire_boite(boite)
        if args.reply_to and not any(m["id"] == args.reply_to for m in data["messages"]):
            raise SystemExit(f"--reply-to : message introuvable : {args.reply_to}")
        message = {
            "id": nouvel_id(data, de),
            "date": maintenant(),
            "de": de,
            "a": dest,
            "objet": objet,
            "corps": corps,
            "pj": pj,
            "re": args.reply_to,
            "statut": "nouveau",
            "historique": [],
        }
        data["messages"].append(message)
        enregistrer_boite(boite, data)
    print(message["id"])
    return 0


def cmd_check(args):
    try:
        boite = boite_de(args, obligatoire=False)
        agent = agent_de(args)
        trouves = pour(lire_boite(boite), agent) if boite else []
    except (OSError, SystemExit):
        return 0  # une relève ne bloque jamais une session : silence si la boîte est injoignable
    if not trouves:
        return 0
    if args.json:
        (sys.stderr if args.wake else sys.stdout).write(en_json({"agent": agent, "nouveaux": trouves}))
        return 2 if args.wake else 0
    sortie = [f"COURRIER — {len(trouves)} message(s) au statut « nouveau » pour {agent}.",
              f"Boîte : {boite}", *[resume(m) for m in trouves],
              f"À faire : lire chaque pièce jointe, agir, puis `messenger.py mark --agent {agent} --id <id> --status lu|traité`."]
    (sys.stderr if args.wake else sys.stdout).write("\n".join(sortie) + "\n")
    return 2 if args.wake else 0


def cmd_mark(args):
    boite, agent = boite_de(args), agent_de(args)
    with verrou(boite):
        data = lire_boite(boite)
        cible = next((m for m in data["messages"] if m["id"] == args.id), None)
        if not cible:
            raise SystemExit(f"message introuvable : {args.id}")
        if agent not in cible["a"]:
            raise SystemExit(f"{agent} n'est pas destinataire de {args.id} : seul un destinataire fait avancer le statut")
        actuel = STATUTS.index(cible["statut"]) if cible["statut"] in STATUTS else -1
        if STATUTS.index(args.status) <= actuel:
            raise SystemExit(f"{args.id} est déjà « {cible['statut']} » : un statut ne recule pas")
        cible["statut"] = args.status
        cible.setdefault("historique", []).append({"date": maintenant(), "par": agent, "statut": args.status})
        enregistrer_boite(boite, data)
    print(f"{args.id} → {args.status}")
    return 0


def cmd_list(args):
    data = lire_boite(boite_de(args))
    liste = list(reversed(data["messages"]))
    if args.agent:
        liste = [m for m in liste if args.agent in m["a"] or m["de"] == args.agent]
    if args.status:
        liste = [m for m in liste if m["statut"] == args.status]
    liste = liste[: args.limit]
    if args.json:
        print(en_json(liste), end="")
        return 0
    for m in liste:
        print(f"{m['statut']:8} {resume(m)}")
    return 0


def cmd_watch(args):
    """Rend la main dès qu'un NOUVEAU message « nouveau » arrive pour l'agent.

    La base est l'ensemble des messages déjà en attente au démarrage : les
    écritures de l'agent lui-même et les changements de statut ne réveillent
    jamais. À lancer en tâche de fond ; relancer après chaque réveil.
    """
    boite, agent = boite_de(args), agent_de(args)
    base = {m["id"] for m in pour(lire_boite(boite), agent)}
    fin = time.time() + args.max_hours * 3600
    while time.time() < fin:
        time.sleep(args.interval)
        try:
            recus = [m for m in pour(lire_boite(boite), agent) if m["id"] not in base]
        except (OSError, SystemExit):
            continue  # boîte momentanément injoignable ou en cours d'écriture : on réessaie
        if recus:
            print(f"COURRIER — {len(recus)} nouveau(x) message(s) pour {agent}.")
            for m in recus:
                print(resume(m))
            return 0
    print(f"aucun message pour {agent} en {args.max_hours:g} h")
    return 3


# --------------------------------------------------------------------------- #
# Migration d'une boîte Markdown (format « ### id · objet » + ligne d'adresse)
# --------------------------------------------------------------------------- #
RE_BLOC = re.compile(r"(?m)^### ")
RE_ID = re.compile(r"^(\d{8}-\d{4}-[A-Za-z0-9_.-]+?(?:-\d+)?)\s")
RE_DE = re.compile(r"\*\*De\*\*\s*([^\s→]+)")
RE_A = re.compile(r"\*\*À\*\*\s*(.+?)\s*·")
RE_STATUT = re.compile(r"\*\*Statut\*\*\s*(\S+)")
RE_PJ = re.compile(r"\*\*PJ\*\*\s*(.+)$")
RE_LIEN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RE_RE = re.compile(r"^Re\s*:\s*(\S+)\s*[—-]\s*(.*)$")


def depuis_markdown(texte):
    messages = []
    _, _, corps_boite = texte.partition("## Messages")
    for bloc in RE_BLOC.split(corps_boite)[1:]:
        lignes = bloc.splitlines()
        entete = lignes[0].strip()
        m = RE_ID.match(entete + " ")
        adresse = next((l for l in lignes if RE_STATUT.search(l)), None)
        if not m or not adresse:
            continue
        mid = m.group(1)
        objet = entete[len(mid):].lstrip(" ·").strip()
        re_ = None
        r = RE_RE.match(objet)
        if r:
            re_, objet = r.group(1), r.group(2).strip()
        pj_brut = (RE_PJ.search(adresse).group(1).strip() if RE_PJ.search(adresse) else "—")
        pj = RE_LIEN.search(pj_brut).group(1) if RE_LIEN.search(pj_brut) else None
        date = dt.datetime.strptime(mid[:13], "%Y%m%d-%H%M").isoformat(timespec="seconds")
        messages.append({
            "id": mid,
            "date": date,
            "de": RE_DE.search(adresse).group(1) if RE_DE.search(adresse) else "?",
            "a": [x.strip() for x in (RE_A.search(adresse).group(1) if RE_A.search(adresse) else "").split(",") if x.strip()],
            "objet": objet,
            "corps": [l.rstrip() for l in lignes[1:] if l.strip() and l is not adresse and not RE_STATUT.search(l)],
            "pj": pj,
            "re": re_,
            "statut": RE_STATUT.search(adresse).group(1),
            "historique": [],
            "importe": True,
        })
    return list(reversed(messages))  # la boîte Markdown est du plus récent au plus ancien


def cmd_migrate(args):
    source = os.path.expanduser(args.source)
    boite = boite_de(args)
    if os.path.exists(boite):
        raise SystemExit(f"la boîte JSON existe déjà, rien écrit : {boite}")
    with open(source, encoding="utf-8") as f:
        messages = depuis_markdown(f.read())
    if not messages:
        raise SystemExit(f"aucun message reconnu dans {source}")
    os.makedirs(os.path.dirname(os.path.abspath(boite)), exist_ok=True)
    enregistrer_boite(boite, {"version": FORMAT, "messages": messages})
    noms = sorted({m["de"] for m in messages} | {d for m in messages for d in m["a"]})
    m = lire_manifeste(boite) or manifeste_vide(boite)
    connus = {c["nom"] for c in m.get("comptes", [])}
    for nom in noms:
        if nom not in connus and RE_NOM.match(nom):
            m["comptes"].append({"nom": nom, "hote": "inconnu", "role": "compte importé — à compléter par son agent (register --update)",
                                 "cree": maintenant(), "actif": True})
    ecrire_manifeste(boite, m)
    print(f"{len(messages)} messages importés dans {boite}")
    print(f"comptes importés, à compléter par chaque agent : {', '.join(noms)}")
    return 0


def main(argv=None):
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="messenger.py", description="Boîte aux lettres JSON partagée entre agents IA.")
    p.add_argument("--version", action="version", version=VERSION)
    s = p.add_subparsers(dest="cmd", required=True)

    def commune(sp, agent=True):
        sp.add_argument("--box", help="chemin de la boîte .json (sinon MESSENGER_BOX, sinon setup)")
        if agent:
            sp.add_argument("--agent", help="ton nom d'agent (sinon MESSENGER_AGENT)")
        return sp

    x = commune(s.add_parser("init", help="crée une boîte vide"), agent=False); x.set_defaults(f=cmd_init)
    x = commune(s.add_parser("setup", help="mémorise la boîte pour ce poste"), agent=False); x.set_defaults(f=cmd_setup)
    x = commune(s.add_parser("register", help="crée ou met à jour ton compte"))
    x.add_argument("--host", required=True, help="ton hôte : claude-code, kimi-code, codex, hermes, humain, autre…")
    x.add_argument("--role", required=True, help="en une ligne : ce que tu fais, pour qu'on sache quand t'écrire")
    x.add_argument("--machine", help="où tu tournes (défaut : nom du poste)")
    x.add_argument("--model", help="ton modèle, si utile")
    x.add_argument("--human", help="l'humain responsable")
    x.add_argument("--wake", help="comment tu relèves ton courrier (hooks, watch…)")
    x.add_argument("--update", action="store_true", help="mettre à jour ton compte existant")
    x.set_defaults(f=cmd_register)
    x = commune(s.add_parser("agents", help="liste les comptes"), agent=False)
    x.add_argument("--all", action="store_true", help="inclure les comptes désactivés")
    x.add_argument("--json", action="store_true", help="sortie JSON (le manifeste)")
    x.set_defaults(f=cmd_agents)
    x = commune(s.add_parser("deactivate", help="désactive un compte (jamais supprimé)")); x.set_defaults(f=cmd_deactivate)
    x = commune(s.add_parser("send", help="poste un message"))
    x.add_argument("--to", required=True, help="destinataires, séparés par des virgules")
    x.add_argument("--subject", required=True)
    x.add_argument("--body", default="", help="deux lignes au plus")
    x.add_argument("--attach", help="fichier joint (copié dans le dossier de la boîte s'il n'y est pas)")
    x.add_argument("--reply-to", help="identifiant du message auquel tu réponds")
    x.set_defaults(f=cmd_send)
    x = commune(s.add_parser("check", help="relève le courrier « nouveau » (hooks)"))
    x.add_argument("--wake", action="store_true", help="résumé sur stderr et code 2 s'il y a du courrier")
    x.add_argument("--json", action="store_true", help="sortie JSON")
    x.set_defaults(f=cmd_check)
    x = commune(s.add_parser("mark", help="fait avancer le statut d'un message reçu"))
    x.add_argument("--id", required=True); x.add_argument("--status", required=True, choices=STATUTS[1:])
    x.set_defaults(f=cmd_mark)
    x = commune(s.add_parser("list", help="affiche les messages, du plus récent au plus ancien"))
    x.add_argument("--status", choices=STATUTS); x.add_argument("--limit", type=int, default=20)
    x.add_argument("--json", action="store_true", help="sortie JSON")
    x.set_defaults(f=cmd_list)
    x = commune(s.add_parser("watch", help="attend le prochain message pour un agent"))
    x.add_argument("--interval", type=float, default=10.0, help="secondes entre deux relèves")
    x.add_argument("--max-hours", type=float, default=12.0)
    x.set_defaults(f=cmd_watch)
    x = commune(s.add_parser("migrate", help="importe une boîte Markdown existante"), agent=False)
    x.add_argument("--from", dest="source", required=True, help="la boîte Markdown à importer")
    x.set_defaults(f=cmd_migrate)
    args = p.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    sys.exit(main())
