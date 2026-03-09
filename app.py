import os
import random
import string
import json
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, emit
import redis

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'undercover-secret-key-change-in-prod')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', allow_upgrades=False)

# -------------------------------------------------------
# REDIS
# -------------------------------------------------------
redis_client = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))

def sauver_partie(code, partie):
    redis_client.setex(f"partie:{code}", 3600, json.dumps(partie))

def get_partie(code):
    data = redis_client.get(f"partie:{code}")
    return json.loads(data) if data else None

def supprimer_partie(code):
    redis_client.delete(f"partie:{code}")

# -------------------------------------------------------
# THÈMES
# -------------------------------------------------------
THEMES = {
    "Nuit": {
        "civil":     "https://res.cloudinary.com/dzgy637iz/video/upload/v1772999688/1_Braquage_nuit_k34icx.mp4",
        "imposteur": "https://res.cloudinary.com/dzgy637iz/video/upload/v1772999689/2_Braquage_nuit_pr1nq7.mp4",
    },
    "Image": {
        "civil":     "https://res.cloudinary.com/dzgy637iz/image/upload/v1772999727/1_image_ix6jmq.png",
        "imposteur": "https://res.cloudinary.com/dzgy637iz/image/upload/v1772999729/2_image_wzsczs.png",
    },
}

# -------------------------------------------------------
# UTILITAIRES
# -------------------------------------------------------
def generer_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=6))
        if not get_partie(code):
            return code

# -------------------------------------------------------
# ROUTES
# -------------------------------------------------------
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
        'code':          code,
        'hote':          pseudo,
        'nb_manches':    nb_manches,
        'avec_mr_white': avec_mr_white,
        'manche':        1,
        'phase':         'lobby',
        'joueurs':       {},
        'ordre_tours':   [],
        'tour_actuel':   0,
        'votes':         {},
        'theme_actuel':  None,
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
        return render_template('accueil.html', erreur="Code invalide !")
    if partie['phase'] != 'lobby':
        return render_template('accueil.html', erreur="La partie a déjà commencé !")

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
    sid    = request.args.get('sid')
    joueur = partie['joueurs'].get(sid, {})
    return jsonify({
        'phase':       partie['phase'],
        'manche':      partie['manche'],
        'nb_manches':  partie['nb_manches'],
        'role':        joueur.get('role'),
        'video_url':   joueur.get('video_url'),
        'joueurs':     [j['pseudo'] for j in partie['joueurs'].values()],
        'tour_actuel': partie['tour_actuel'],
        'ordre_tours': [partie['joueurs'].get(s, {}).get('pseudo') for s in partie['ordre_tours']],
    })

# -------------------------------------------------------
# SOCKETIO — LOBBY
# -------------------------------------------------------
@socketio.on('rejoindre_lobby')
def on_rejoindre_lobby(data):
    code   = data.get('code', '').upper()
    pseudo = data.get('pseudo', 'Joueur')
    print(f">>> rejoindre_lobby : code={code}, pseudo={pseudo}")

    partie = get_partie(code)
    if not partie:
        print(f">>> partie {code} introuvable !")
        return

    join_room(code)
    partie['joueurs'][request.sid] = {
        'pseudo':    pseudo,
        'role':      None,
        'video_url': None,
        'pret':      False,
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

    sids = list(partie['joueurs'].keys())
    if len(sids) < 3:
        emit('erreur', {'message': 'Il faut au moins 3 joueurs !'})
        return

    _distribuer_roles(partie)
    sauver_partie(code, partie)
    emit('partie_lancee', {'code': code}, to=code)

def _distribuer_roles(partie):
    sids  = list(partie['joueurs'].keys())
    random.shuffle(sids)
    partie['ordre_tours'] = sids
    partie['tour_actuel'] = 0
    partie['votes']       = {}
    partie['phase']       = 'tour'

    nom_theme = random.choice(list(THEMES.keys()))
    theme     = THEMES[nom_theme]
    partie['theme_actuel'] = nom_theme

    imposteur_sid = random.choice(sids)
    mr_white_sid  = None
    if partie['avec_mr_white'] and len(sids) >= 4:
        restants     = [s for s in sids if s != imposteur_sid]
        mr_white_sid = random.choice(restants)

    for sid in sids:
        if sid == imposteur_sid:
            role      = 'imposteur'
            video_url = theme['imposteur']
        elif sid == mr_white_sid:
            role      = 'mr_white'
            video_url = None
        else:
            role      = 'civil'
            video_url = theme['civil']

        partie['joueurs'][sid]['role']      = role
        partie['joueurs'][sid]['video_url'] = video_url

# -------------------------------------------------------
# SOCKETIO — JEU
# -------------------------------------------------------
@socketio.on('rejoindre_jeu')
def on_rejoindre_jeu(data):
    code   = data.get('code', '').upper()
    partie = get_partie(code)
    if not partie:
        return

    join_room(code)
    joueur = partie['joueurs'].get(request.sid)
    if not joueur:
        return

    emit('ton_role', {
        'role':      joueur['role'],
        'video_url': joueur['video_url'],
        'pseudo':    joueur['pseudo'],
    })
    _emettre_etat_tour(partie, code)

def _emettre_etat_tour(partie, code):
    ordre         = [partie['joueurs'].get(s, {}).get('pseudo', '?') for s in partie['ordre_tours']]
    actuel_idx    = partie['tour_actuel']
    actuel_pseudo = ordre[actuel_idx] if actuel_idx < len(ordre) else None

    socketio.emit('etat_tour', {
        'ordre':         ordre,
        'actuel_pseudo': actuel_pseudo,
        'actuel_idx':    actuel_idx,
        'total':         len(ordre),
        'manche':        partie['manche'],
        'nb_manches':    partie['nb_manches'],
    }, to=code)

@socketio.on('tour_termine')
def on_tour_termine(data):
    code   = data.get('code', '').upper()
    partie = get_partie(code)
    if not partie:
        return

    partie['tour_actuel'] += 1
    if partie['tour_actuel'] >= len(partie['ordre_tours']):
        partie['phase'] = 'vote'
        sauver_partie(code, partie)
        socketio.emit('passer_au_vote', {}, to=code)
    else:
        sauver_partie(code, partie)
        _emettre_etat_tour(partie, code)

@socketio.on('voter')
def on_voter(data):
    code   = data.get('code', '').upper()
    cible  = data.get('cible')
    partie = get_partie(code)
    if not partie:
        return

    partie['votes'][request.sid] = cible
    sauver_partie(code, partie)

    if len(partie['votes']) >= len(partie['joueurs']):
        _calculer_resultat(partie, code)

def _calculer_resultat(partie, code):
    comptage = {}
    for cible in partie['votes'].values():
        comptage[cible] = comptage.get(cible, 0) + 1

    elu       = max(comptage, key=comptage.get)
    imposteur = next((j for j in partie['joueurs'].values() if j['role'] == 'imposteur'), None)
    mr_white  = next((j for j in partie['joueurs'].values() if j['role'] == 'mr_white'), None)

    victoire_civils = imposteur and elu == imposteur['pseudo']

    socketio.emit('resultat', {
        'elu':             elu,
        'victoire_civils': victoire_civils,
        'imposteur':       imposteur['pseudo'] if imposteur else '?',
        'mr_white':        mr_white['pseudo'] if mr_white else None,
        'theme':           partie['theme_actuel'],
        'votes':           comptage,
        'manche':          partie['manche'],
        'nb_manches':      partie['nb_manches'],
    }, to=code)

    partie['phase'] = 'resultat'
    sauver_partie(code, partie)

@socketio.on('manche_suivante')
def on_manche_suivante(data):
    code   = data.get('code', '').upper()
    partie = get_partie(code)
    if not partie:
        return

    if partie['manche'] >= partie['nb_manches']:
        partie['phase'] = 'fin'
        sauver_partie(code, partie)
        socketio.emit('fin_partie', {}, to=code)
        return

    partie['manche'] += 1
    _distribuer_roles(partie)
    sauver_partie(code, partie)
    socketio.emit('nouvelle_manche', {'manche': partie['manche']}, to=code)

@socketio.on('disconnect')
def on_disconnect():
    # Cherche dans toutes les parties actives
    for key in redis_client.scan_iter("partie:*"):
        partie = json.loads(redis_client.get(key))
        if request.sid in partie['joueurs']:
            code   = partie['code']
            pseudo = partie['joueurs'][request.sid]['pseudo']
            del partie['joueurs'][request.sid]
            sauver_partie(code, partie)
            emit('joueur_parti', {'pseudo': pseudo}, to=code)
            if not partie['joueurs']:
                supprimer_partie(code)
            break

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)