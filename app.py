# =============================
# app.py (version stabilisée)
# =============================

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

    pseudo = request.form.get('pseudo', 'Hôte').strip()
    nb_manches = int(request.form.get('nb_manches', 3))
    avec_mr_white = request.form.get('mr_white') == 'on'

    code = generer_code()

    partie = {
        'code': code,
        'hote': pseudo,
        'nb_manches': nb_manches,
        'avec_mr_white': avec_mr_white,
        'manche': 1,
        'phase': 'lobby',
        'joueurs': {},
        'votes': {},
        'theme_actuel': None,
    }

    sauver_partie(code, partie)

    session['code'] = code
    session['pseudo'] = pseudo
    session['est_hote'] = True

    return redirect(url_for('lobby', code=code))


@app.route('/rejoindre', methods=['POST'])
def rejoindre():

    pseudo = request.form.get('pseudo', 'Joueur').strip()
    code = request.form.get('code', '').upper().strip()

    partie = get_partie(code)

    if not partie:
        return render_template('accueil.html', erreur="Code invalide")

    if partie['phase'] != 'lobby':
        return render_template('accueil.html', erreur="Partie déjà lancée")

    session['code'] = code
    session['pseudo'] = pseudo
    session['est_hote'] = False

    return redirect(url_for('lobby', code=code))


@app.route('/lobby/<code>')
def lobby(code):

    partie = get_partie(code)

    if not partie:
        return redirect(url_for('accueil'))

    return render_template(
        'lobby.html',
        code=code,
        pseudo=session.get('pseudo'),
        est_hote=session.get('est_hote', False),
        nb_manches=partie['nb_manches'],
        avec_mr_white=partie['avec_mr_white'],
    )


@app.route('/jeu/<code>')
def jeu(code):

    partie = get_partie(code)

    if not partie:
        return redirect(url_for('accueil'))

    return render_template(
        'jeu.html',
        code=code,
        pseudo=session.get('pseudo'),
        est_hote=session.get('est_hote', False),
    )


@app.route('/api/partie/<code>')
def api_partie(code):

    partie = get_partie(code)

    if not partie:
        return jsonify({'erreur': 'Partie introuvable'}), 404

    return jsonify({
        'phase': partie['phase'],
        'manche': partie['manche'],
        'nb_manches': partie['nb_manches'],
        'joueurs': [j['pseudo'] for j in partie['joueurs'].values()],
    })


# ------------------------------
# ROLE DISTRIBUTION
# ------------------------------

def distribuer_roles(code):

    partie = get_partie(code)

    sids = list(partie['joueurs'].keys())

    random.shuffle(sids)

    # choisir une scène
    scene = random.choice(SCENES)
    print("SCENE CHOISIE:", scene["nom"])

    civil_url = scene["civil"]
    imposteur_url = scene["imposteur"]

    partie['theme_actuel'] = scene["nom"]

    imposteur_sid = random.choice(sids)

    for sid in sids:

        if sid == imposteur_sid:

            role = "imposteur"
            url = imposteur_url

        else:

            role = "civil"
            url = civil_url

        partie['joueurs'][sid]['role'] = role
        partie['joueurs'][sid]['video_url'] = url

    sauver_partie(code, partie)

    for sid, j in partie['joueurs'].items():

        socketio.emit('ton_role', {
            'role': j['role'],
            'video_url': j['video_url'],
            'pseudo': j['pseudo'],
        }, to=sid)


# ------------------------------
# SOCKET LOBBY
# ------------------------------

@socketio.on('rejoindre_lobby')
def on_rejoindre_lobby(data):

    code = data.get('code', '').upper()
    pseudo = data.get('pseudo')

    if not pseudo:
        return

    partie = get_partie(code)

    if not partie:
        return

    join_room(code)

    # supprimer les anciens joueurs avec le même pseudo
    anciens = []

    for sid, j in partie['joueurs'].items():
        if j['pseudo'] == pseudo:
            anciens.append(sid)

    for sid in anciens:
        del partie['joueurs'][sid]

    # ajouter le joueur
    partie['joueurs'][request.sid] = {
        'pseudo': pseudo,
        'role': None,
        'video_url': None,
        'pret': False,
        'sid': request.sid,
    }

    sauver_partie(code, partie)

    emit('mise_a_jour_lobby', {
        'joueurs': [j['pseudo'] for j in partie['joueurs'].values()],
        'nb': len(partie['joueurs']),
    }, to=code)

@socketio.on('lancer_partie')

def on_lancer_partie(data):

    code = data.get('code', '').upper()

    partie = get_partie(code)

    if not partie:
        return

    if len(partie['joueurs']) < 3:
        emit('erreur', {'message': 'Il faut au moins 3 joueurs'})
        return

    partie['phase'] = 'chargement'

    sauver_partie(code, partie)

    socketio.emit('partie_lancee', {'code': code}, to=code)


# ------------------------------
# SOCKET JEU
# ------------------------------

@socketio.on('rejoindre_jeu')

def rejoindre_jeu(data):

    code = data.get('code', '').upper()
    pseudo = data.get('pseudo', '')

    partie = get_partie(code)

    if not partie:
        return

    join_room(code)

    for sid, j in list(partie['joueurs'].items()):

        if j['pseudo'] == pseudo:

            if sid != request.sid:

                partie['joueurs'][request.sid] = j
                del partie['joueurs'][sid]

            break

    sauver_partie(code, partie)

    if partie['phase'] in ['chargement', 'visionnage']:

        distribuer_roles(code)


@socketio.on('joueur_pret')

def joueur_pret(data):

    code = data.get('code', '').upper()
    pseudo = data.get('pseudo', '')

    partie = get_partie(code)

    if not partie:
        return

    for sid, j in partie['joueurs'].items():

        if j['pseudo'] == pseudo:

            j['pret'] = True

    sauver_partie(code, partie)

    nb_prets = sum(1 for j in partie['joueurs'].values() if j.get('pret'))

    total = len(partie['joueurs'])

    socketio.emit('nb_prets', {'nb': nb_prets, 'total': total}, to=code)

    if nb_prets >= total:

        partie['phase'] = 'vote'

        sauver_partie(code, partie)

        socketio.emit('tout_le_monde_pret', {}, to=code)


@socketio.on('voter')

def voter(data):

    code = data.get('code', '').upper()

    cible = data.get('cible')

    partie = get_partie(code)

    if not partie:
        return

    if partie['phase'] != 'vote':
        return

    partie['votes'][request.sid] = cible

    sauver_partie(code, partie)

    if len(partie['votes']) >= len(partie['joueurs']):

        calculer_resultat(code)


# ------------------------------
# RESULTATS
# ------------------------------

def calculer_resultat(code):

    partie = get_partie(code)

    if not partie:
        return

    comptage = {}

    for cible in partie['votes'].values():

        comptage[cible] = comptage.get(cible, 0) + 1

    elu = max(comptage, key=comptage.get)

    imposteur = next((j for j in partie['joueurs'].values() if j['role'] == 'imposteur'), None)

    victoire = imposteur and elu == imposteur['pseudo']

    socketio.emit('resultat', {
        'elu': elu,
        'victoire_civils': victoire,
        'imposteur': imposteur['pseudo'],
        'theme': partie['theme_actuel'],
        'votes': comptage,
        'manche': partie['manche'],
        'nb_manches': partie['nb_manches'],
    }, to=code)

    partie['phase'] = 'resultat'

    sauver_partie(code, partie)


@socketio.on('manche_suivante')

def manche_suivante(data):

    code = data.get('code', '').upper()

    partie = get_partie(code)

    if not partie:
        return

    if partie['manche'] >= partie['nb_manches']:

        socketio.emit('fin_partie', {}, to=code)

        return

    partie['manche'] += 1

    sauver_partie(code, partie)

    distribuer_roles(code)


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

@socketio.on('disconnect')
def on_disconnect():

    for key in redis_client.scan_iter("partie:*"):

        partie = json.loads(redis_client.get(key))

        if request.sid in partie['joueurs']:

            code = partie['code']

            del partie['joueurs'][request.sid]

            sauver_partie(code, partie)

            break