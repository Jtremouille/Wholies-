import os
import random
import string
import json
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, emit
import redis

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'undercover-secret-key-change-in-prod')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', allow_upgrades=False)

redis_client = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))

# ------------------------------
# REDIS HELPERS
# ------------------------------

def sauver_partie(code, partie):
    redis_client.setex(f"partie:{code}", 3600, json.dumps(partie))

def get_partie(code):
    data = redis_client.get(f"partie:{code}")
    return json.loads(data) if data else None

def supprimer_partie(code):
    redis_client.delete(f"partie:{code}")

# ------------------------------
# THEMES
# ------------------------------

SCENES = [
    {
        "nom": "Nuit",
        "civil": "https://res.cloudinary.com/dzgy637iz/video/upload/v1772999688/1_Braquage_nuit_k34icx.mp4",
        "imposteur": "https://res.cloudinary.com/dzgy637iz/video/upload/v1772999689/2_Braquage_nuit_pr1nq7.mp4"
    },
    {
        "nom": "Image",
        "civil": "https://res.cloudinary.com/dzgy637iz/image/upload/v1772999727/1_image_ix6jmq.png",
        "imposteur": "https://res.cloudinary.com/dzgy637iz/image/upload/v1772999729/2_image_wzsczs.png"
    },
]

# ------------------------------
# UTIL
# ------------------------------

def generer_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=6))
        if not get_partie(code):
            return code

# ------------------------------
# ROUTES
# ------------------------------

@app.route('/')
def accueil():
    return render_template('accueil.html')

@app.route('/creer', methods=['POST'])
def creer_partie():
    pseudo        = request.form.get('pseudo', 'Hôte').strip()
    nb_manches    = int(request.form.get('nb_manches', 3))
    avec_mr_white = request.form.get('mr_white') == 'on'

    code = generer_code()
    partie = {
        'code':             code,
        'hote':             pseudo,
        'nb_manches':       nb_manches,
        'avec_mr_white':    avec_mr_white,
        'manche':           1,
        'phase':            'lobby',
        'joueurs':          {},
        'votes':            {},
        'theme_actuel':     None,
        'scenes_restantes': SCENES.copy(),
        'scores':           {},       # pseudo -> points cumulés
        'host_sid':         None,
        # Pour synchroniser l'arrivée sur /jeu avant de distribuer
        'nb_attendus':      0,
        'joueurs_prets_jeu': [],
    }
    sauver_partie(code, partie)
    session['code']     = code
    session['pseudo']   = pseudo
    session['est_hote'] = True
    return redirect(url_for('lobby', code=code))

@app.route('/rejoindre', methods=['POST'])
def rejoindre():
    pseudo = request.form.get('pseudo', 'Joueur').strip()
    code   = request.form.get('code', '').upper().strip()
    partie = get_partie(code)
    if not partie:
        return render_template('accueil.html', erreur="Code invalide")
    if partie['phase'] != 'lobby':
        return render_template('accueil.html', erreur="Partie déjà lancée")
    session['code']     = code
    session['pseudo']   = pseudo
    session['est_hote'] = False
    return redirect(url_for('lobby', code=code))

@app.route('/lobby/<code>')
def lobby(code):
    partie = get_partie(code)
    if not partie:
        return redirect(url_for('accueil'))
    return render_template('lobby.html',
                           code=code,
                           pseudo=session.get('pseudo'),
                           est_hote=session.get('est_hote', False),
                           nb_manches=partie['nb_manches'],
                           avec_mr_white=partie['avec_mr_white'])

@app.route('/jeu/<code>')
def jeu(code):
    partie = get_partie(code)
    if not partie:
        return redirect(url_for('accueil'))
    return render_template('jeu.html',
                           code=code,
                           pseudo=session.get('pseudo'),
                           est_hote=session.get('est_hote', False))

@app.route('/api/partie/<code>')
def api_partie(code):
    partie = get_partie(code)
    if not partie:
        return jsonify({'erreur': 'Partie introuvable'}), 404
    return jsonify({
        'phase':      partie['phase'],
        'manche':     partie['manche'],
        'nb_manches': partie['nb_manches'],
        'joueurs':    [j['pseudo'] for j in partie['joueurs'].values() if j.get('pseudo')],
    })

# ------------------------------
# DISTRIBUTION DES RÔLES
# ------------------------------

def distribuer_roles(code):
    partie = get_partie(code)
    if not partie:
        return

    sids = list(partie['joueurs'].keys())
    if len(sids) < 2:
        return

    # Reset
    for j in partie['joueurs'].values():
        j['pret']      = False
        j['vote']      = None
        j['role']      = None
        j['video_url'] = None

    partie['votes'] = {}
    partie['phase'] = 'visionnage'

    # Choisir une scène sans répétition
    if not partie.get('scenes_restantes'):
        partie['scenes_restantes'] = SCENES.copy()

    scene = random.choice(partie['scenes_restantes'])
    partie['scenes_restantes'] = [s for s in partie['scenes_restantes'] if s['nom'] != scene['nom']]
    partie['theme_actuel'] = scene['nom']

    print(f">>> SCENE CHOISIE: {scene['nom']}")

    # Choisir l'imposteur
    imposteur_sid = random.choice(sids)
    print(f">>> IMPOSTEUR: {partie['joueurs'][imposteur_sid]['pseudo']}")

    for sid in sids:
        if sid == imposteur_sid:
            partie['joueurs'][sid]['role']      = 'imposteur'
            partie['joueurs'][sid]['video_url'] = scene['imposteur']
        else:
            partie['joueurs'][sid]['role']      = 'civil'
            partie['joueurs'][sid]['video_url'] = scene['civil']

    sauver_partie(code, partie)

    print(f">>> DISTRIBUTION: {[(j['pseudo'], j['role']) for j in partie['joueurs'].values()]}")

    # Envoyer les rôles
    for sid, j in partie['joueurs'].items():
        socketio.emit('ton_role', {
            'role':      j['role'],
            'video_url': j['video_url'],
            'pseudo':    j['pseudo'],
        }, to=sid)

# ------------------------------
# SOCKET LOBBY
# ------------------------------

@socketio.on('rejoindre_lobby')
def on_rejoindre_lobby(data):
    code   = data.get('code', '').upper()
    pseudo = (data.get('pseudo') or '').strip()
    if not pseudo:
        return

    partie = get_partie(code)
    if not partie:
        return

    join_room(code)

    if partie.get('host_sid') is None:
        partie['host_sid'] = request.sid

    # Supprimer les doublons
    anciens = [sid for sid, j in partie['joueurs'].items() if j['pseudo'] == pseudo]
    for sid in anciens:
        del partie['joueurs'][sid]

    partie['joueurs'][request.sid] = {
        'pseudo':    pseudo,
        'role':      None,
        'video_url': None,
        'pret':      False,
        'vote':      None,
        'sid':       request.sid,
    }
    sauver_partie(code, partie)

    emit('mise_a_jour_lobby', {
        'joueurs': [j['pseudo'] for j in partie['joueurs'].values()],
        'nb':      len(partie['joueurs']),
    }, to=code)

@socketio.on('lancer_partie')
def on_lancer_partie(data):
    code   = data.get('code', '').upper()
    partie = get_partie(code)
    if not partie or partie['phase'] != 'lobby':
        return

    nb = len(partie['joueurs'])
    if nb < 3:
        emit('erreur', {'message': 'Il faut au moins 3 joueurs'})
        return

    # On note combien de joueurs on attend sur /jeu avant de distribuer
    partie['phase']            = 'chargement'
    partie['nb_attendus']      = nb
    partie['joueurs_prets_jeu'] = []
    sauver_partie(code, partie)

    socketio.emit('partie_lancee', {'code': code}, to=code)

# ------------------------------
# SOCKET JEU
# ------------------------------

@socketio.on('rejoindre_jeu')
def on_rejoindre_jeu(data):
    code   = data.get('code', '').upper()
    pseudo = (data.get('pseudo') or '').strip()
    if not pseudo:
        return

    partie = get_partie(code)
    if not partie:
        return

    join_room(code)

    # Mettre à jour le sid
    for sid, j in list(partie['joueurs'].items()):
        if j['pseudo'] == pseudo:
            if sid != request.sid:
                partie['joueurs'][request.sid] = j
                partie['joueurs'][request.sid]['sid'] = request.sid
                del partie['joueurs'][sid]
            break

    # Marquer ce joueur comme arrivé sur /jeu (une seule fois)
    prets_jeu = partie.get('joueurs_prets_jeu', [])
    if pseudo not in prets_jeu:
        prets_jeu.append(pseudo)
    partie['joueurs_prets_jeu'] = prets_jeu

    sauver_partie(code, partie)

    nb_attendus = partie.get('nb_attendus', 0)
    print(f">>> rejoindre_jeu: {pseudo} | {len(prets_jeu)}/{nb_attendus} arrivés")

    # Distribuer une seule fois quand tout le monde est là
    # On relit la partie depuis Redis pour éviter la race condition
    partie_fraiche = get_partie(code)
    if (partie_fraiche.get('phase') == 'chargement'
            and nb_attendus > 0
            and len(partie_fraiche.get('joueurs_prets_jeu', [])) >= nb_attendus):
        distribuer_roles(code)


@socketio.on('joueur_pret')
def on_joueur_pret(data):
    code   = data.get('code', '').upper()
    pseudo = (data.get('pseudo') or '').strip()
    partie = get_partie(code)
    if not partie:
        return

    for sid, j in partie['joueurs'].items():
        if j['pseudo'] == pseudo:
            j['pret'] = True
            break

    sauver_partie(code, partie)

    nb_prets = sum(1 for j in partie['joueurs'].values() if j.get('pret'))
    total    = len(partie['joueurs'])
    print(f">>> joueur_pret: {nb_prets}/{total}")

    socketio.emit('nb_prets', {'nb': nb_prets, 'total': total}, to=code)

    if nb_prets >= total:
        partie['phase'] = 'vote'
        sauver_partie(code, partie)
        socketio.emit('tout_le_monde_pret', {}, to=code)

@socketio.on('voter')
def on_voter(data):
    code  = data.get('code', '').upper()
    cible = data.get('cible')
    partie = get_partie(code)
    if not partie or partie['phase'] != 'vote':
        return

    partie['votes'][request.sid] = cible
    sauver_partie(code, partie)

    if len(partie['votes']) >= len(partie['joueurs']):
        calculer_resultat(code)

# ------------------------------
# RÉSULTATS
# ------------------------------

def calculer_resultat(code):
    partie = get_partie(code)
    if not partie:
        return

    comptage = {}
    for cible in partie['votes'].values():
        comptage[cible] = comptage.get(cible, 0) + 1

    elu       = max(comptage, key=comptage.get)
    imposteur = next((j for j in partie['joueurs'].values() if j['role'] == 'imposteur'), None)

    victoire_civils = imposteur and elu == imposteur['pseudo']

    # --- Calcul des points ---
    # Civils gagnent (+1 à chaque civil), imposteur gagne (+2 à l'imposteur)
    scores_manche = {}
    if victoire_civils:
        for j in partie['joueurs'].values():
            if j['role'] == 'civil':
                scores_manche[j['pseudo']] = 1
            else:
                scores_manche[j['pseudo']] = 0
    else:
        for j in partie['joueurs'].values():
            if j['role'] == 'imposteur':
                scores_manche[j['pseudo']] = 2
            else:
                scores_manche[j['pseudo']] = 0

    # Ajouter au total
    if 'scores' not in partie:
        partie['scores'] = {}
    for pseudo, pts in scores_manche.items():
        partie['scores'][pseudo] = partie['scores'].get(pseudo, 0) + pts

    partie['phase'] = 'resultat'
    sauver_partie(code, partie)

    socketio.emit('resultat', {
        'elu':             elu,
        'victoire_civils': victoire_civils,
        'imposteur':       imposteur['pseudo'] if imposteur else '?',
        'theme':           partie['theme_actuel'],
        'votes':           comptage,
        'manche':          partie['manche'],
        'nb_manches':      partie['nb_manches'],
        'scores_manche':   scores_manche,
        'scores_total':    partie['scores'],
    }, to=code)

@socketio.on('manche_suivante')
def on_manche_suivante(data):
    code   = data.get('code', '').upper()
    partie = get_partie(code)
    if not partie:
        return

    if partie['manche'] >= partie['nb_manches']:
        # Fin de partie — envoyer les scores finaux
        socketio.emit('fin_partie', {
            'scores': partie.get('scores', {}),
        }, to=code)
        partie['phase'] = 'fin'
        sauver_partie(code, partie)
        return

    partie['manche']            += 1
    partie['votes']              = {}
    partie['joueurs_prets_jeu']  = []
    partie['nb_attendus']        = len(partie['joueurs'])

    for j in partie['joueurs'].values():
        j['pret']      = False
        j['role']      = None
        j['video_url'] = None

    sauver_partie(code, partie)
    socketio.emit('nouvelle_manche', {'manche': partie['manche']}, to=code)
    distribuer_roles(code)

# ------------------------------
# DISCONNECT
# ------------------------------

@socketio.on('disconnect')
def on_disconnect():
    for key in redis_client.scan_iter('partie:*'):
        try:
            partie = json.loads(redis_client.get(key))
        except Exception:
            continue
        if request.sid in partie['joueurs']:
            code   = partie['code']
            pseudo = partie['joueurs'][request.sid]['pseudo']
            del partie['joueurs'][request.sid]
            sauver_partie(code, partie)
            socketio.emit('mise_a_jour_lobby', {
                'joueurs': [j['pseudo'] for j in partie['joueurs'].values()],
                'nb':      len(partie['joueurs']),
            }, to=code)
            break

# ------------------------------
# MAIN
# ------------------------------

if __name__ == '__main__':
    socketio.run(
        app,
        debug=False,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        allow_unsafe_werkzeug=True
    )
