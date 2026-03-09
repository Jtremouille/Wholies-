import tkinter as tk
from tkinter import ttk, messagebox
import requests
from PIL import Image, ImageTk
import io
import random
import webbrowser
import json
import urllib.parse

# -------------------------------------------------------
# THÈMES : (mot_civil, mot_imposteur, lien_youtube)
# -------------------------------------------------------
THEMES = [
    ("plage",       "piscine",      "https://www.youtube.com/results?search_query=plage+mer+vague"),
    ("pizza",       "tarte",        "https://www.youtube.com/results?search_query=pizza+italienne"),
    ("chien",       "loup",         "https://www.youtube.com/results?search_query=chien+mignon"),
    ("football",    "rugby",        "https://www.youtube.com/results?search_query=football+but"),
    ("forêt",       "jungle",       "https://www.youtube.com/results?search_query=forêt+nature"),
    ("voiture",     "moto",         "https://www.youtube.com/results?search_query=voiture+sport"),
    ("château",     "palais",       "https://www.youtube.com/results?search_query=château+france"),
    ("sushi",       "sandwich",     "https://www.youtube.com/results?search_query=sushi+japon"),
    ("astronaute",  "plongeur",     "https://www.youtube.com/results?search_query=astronaute+espace"),
    ("volcan",      "montagne",     "https://www.youtube.com/results?search_query=volcan+eruption"),
]

COULEURS = {
    'bg':       '#0f0f1a',
    'card':     '#1a1a2e',
    'accent':   '#e94560',
    'accent2':  '#0f3460',
    'texte':    '#eaeaea',
    'gris':     '#888888',
    'vert':     '#2ecc71',
    'orange':   '#f39c12',
}

def get_image_url(mot):
    """Cherche une image via DuckDuckGo."""
    try:
        query = urllib.parse.quote(mot)
        url = f"https://api.duckduckgo.com/?q={query}&format=json&iax=images&ia=images"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("Image"):
            return data["Image"]
    except:
        pass
    # Fallback : unsplash
    return f"https://source.unsplash.com/400x300/?{urllib.parse.quote(mot)}"

def get_gif_url(mot):
    """Cherche un GIF via Tenor (sans clé API, mode démo)."""
    try:
        query = urllib.parse.quote(mot)
        url = f"https://tenor.googleapis.com/v2/search?q={query}&key=AIzaSyAyimkuYQYF_FXVALexPzkcsvZnAlbert&limit=5&media_filter=gif"
        r = requests.get(url, timeout=5)
        data = r.json()
        results = data.get("results", [])
        if results:
            gif = random.choice(results)
            return gif["media_formats"]["gif"]["url"]
    except:
        pass
    return None

def charger_image_depuis_url(url, taille=(350, 250)):
    """Télécharge et redimensionne une image depuis une URL."""
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(io.BytesIO(r.content))
        img = img.resize(taille, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except:
        return None


# -------------------------------------------------------
# APPLICATION
# -------------------------------------------------------
class UndercoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🕵️ UNDERCOVER VISUEL")
        self.root.configure(bg=COULEURS['bg'])
        self.root.geometry("700x750")
        self.root.resizable(False, False)

        self.nb_joueurs = 0
        self.joueurs = []       # liste de dicts {nom, role, mot, a_vu}
        self.joueur_actuel = 0
        self.votes = {}
        self.theme = None

        self.frame_actuel = None
        self.afficher_accueil()

    # -------------------------------------------------------
    # UTILITAIRES UI
    # -------------------------------------------------------
    def clear(self):
        if self.frame_actuel:
            self.frame_actuel.destroy()
        self.frame_actuel = tk.Frame(self.root, bg=COULEURS['bg'])
        self.frame_actuel.pack(fill='both', expand=True, padx=30, pady=30)
        return self.frame_actuel

    def titre(self, parent, texte, taille=28, couleur=None):
        tk.Label(parent, text=texte,
                 font=('Georgia', taille, 'bold'),
                 fg=couleur or COULEURS['accent'],
                 bg=COULEURS['bg']).pack(pady=(0, 10))

    def bouton(self, parent, texte, commande, couleur=None, taille=14):
        b = tk.Button(parent, text=texte, command=commande,
                      font=('Courier', taille, 'bold'),
                      fg='white', bg=couleur or COULEURS['accent'],
                      relief='flat', cursor='hand2',
                      padx=20, pady=10, bd=0,
                      activebackground=COULEURS['accent2'],
                      activeforeground='white')
        b.pack(pady=8)
        return b

    def label(self, parent, texte, taille=12, couleur=None):
        tk.Label(parent, text=texte,
                 font=('Courier', taille),
                 fg=couleur or COULEURS['texte'],
                 bg=COULEURS['bg'],
                 wraplength=600,
                 justify='center').pack(pady=4)

    # -------------------------------------------------------
    # ÉCRAN ACCUEIL
    # -------------------------------------------------------
    def afficher_accueil(self):
        f = self.clear()

        tk.Label(f, text="🕵️", font=('Arial', 60), bg=COULEURS['bg']).pack(pady=10)
        self.titre(f, "UNDERCOVER VISUEL", taille=32)
        self.label(f, "Chaque joueur voit une image, un GIF ou une vidéo.\nL'imposteur a un thème légèrement différent.\nDécouvrez qui ment !", taille=11, couleur=COULEURS['gris'])

        tk.Frame(f, bg=COULEURS['accent'], height=2, width=400).pack(pady=15)

        self.label(f, "Nombre de joueurs :", taille=13)

        self.spin_joueurs = tk.Spinbox(f, from_=3, to=12, width=5,
                                       font=('Courier', 20, 'bold'),
                                       justify='center',
                                       bg=COULEURS['card'],
                                       fg=COULEURS['accent'],
                                       buttonbackground=COULEURS['accent2'])
        self.spin_joueurs.pack(pady=10)

        self.bouton(f, "▶  COMMENCER", self.configurer_joueurs)

    # -------------------------------------------------------
    # CONFIGURATION DES NOMS
    # -------------------------------------------------------
    def configurer_joueurs(self):
        try:
            self.nb_joueurs = int(self.spin_joueurs.get())
        except:
            return

        f = self.clear()
        self.titre(f, f"👥 {self.nb_joueurs} joueurs")
        self.label(f, "Entrez les prénoms :", couleur=COULEURS['gris'])

        self.entries_noms = []
        frame_noms = tk.Frame(f, bg=COULEURS['bg'])
        frame_noms.pack(pady=10)

        for i in range(self.nb_joueurs):
            e = tk.Entry(frame_noms, font=('Courier', 13),
                         bg=COULEURS['card'], fg=COULEURS['texte'],
                         insertbackground='white', relief='flat',
                         width=20, justify='center')
            e.insert(0, f"Joueur {i+1}")
            e.pack(pady=4)
            self.entries_noms.append(e)

        self.bouton(f, "✅  VALIDER", self.lancer_partie)

    # -------------------------------------------------------
    # LANCEMENT DE LA PARTIE
    # -------------------------------------------------------
    def lancer_partie(self):
        noms = [e.get().strip() or f"Joueur {i+1}" for i, e in enumerate(self.entries_noms)]

        # Choix du thème
        self.theme = random.choice(THEMES)
        mot_civil, mot_imposteur, lien_yt = self.theme

        # Attribution des rôles (1 imposteur aléatoire)
        imposteur_idx = random.randint(0, self.nb_joueurs - 1)

        self.joueurs = []
        for i, nom in enumerate(noms):
            role = 'imposteur' if i == imposteur_idx else 'civil'
            mot  = mot_imposteur if role == 'imposteur' else mot_civil
            self.joueurs.append({
                'nom':   nom,
                'role':  role,
                'mot':   mot,
                'a_vu':  False,
            })

        random.shuffle(self.joueurs)
        self.joueur_actuel = 0
        self.votes = {}
        self.afficher_tour()

    # -------------------------------------------------------
    # TOUR D'UN JOUEUR
    # -------------------------------------------------------
    def afficher_tour(self):
        f = self.clear()
        joueur = self.joueurs[self.joueur_actuel]

        self.titre(f, f"📱 Au tour de {joueur['nom']}", taille=22)
        self.label(f, "Passe le téléphone / l'écran à ce joueur\npuis appuie sur le bouton.", couleur=COULEURS['gris'])

        self.bouton(f, f"👁  VOIR MON INDICE", self.afficher_indice,
                    couleur=COULEURS['accent2'])

    # -------------------------------------------------------
    # AFFICHAGE DE L'INDICE
    # -------------------------------------------------------
    def afficher_indice(self):
        f = self.clear()
        joueur = self.joueurs[self.joueur_actuel]
        mot = joueur['mot']
        _, _, lien_yt = self.theme

        self.titre(f, f"🎯 Ton indice", taille=20)

        # Choix aléatoire du type de média
        type_media = random.choice(['image', 'gif', 'youtube'])

        if type_media == 'youtube':
            self.label(f, f"🎬 Vidéo YouTube", taille=11, couleur=COULEURS['orange'])
            self.label(f, f"Cherche : « {mot} »", taille=16, couleur=COULEURS['texte'])
            self.bouton(f, "▶  Ouvrir YouTube",
                        lambda: webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(mot)}"),
                        couleur='#FF0000')
        else:
            self.label(f, "⏳ Chargement...", couleur=COULEURS['gris'])
            f.update()

            img_url = get_image_url(mot)
            photo = charger_image_depuis_url(img_url) if img_url else None

            # Supprime le label de chargement
            for w in f.winfo_children():
                if isinstance(w, tk.Label) and "Chargement" in str(w.cget('text')):
                    w.destroy()

            if photo:
                self.photo_ref = photo  # garde une référence
                tk.Label(f, image=photo, bg=COULEURS['bg']).pack(pady=10)
            else:
                self.label(f, f"[ {mot} ]", taille=30, couleur=COULEURS['accent'])

        # Bouton suivant
        nb_restants = self.nb_joueurs - self.joueur_actuel - 1
        if nb_restants > 0:
            self.bouton(f, f"➡  JOUEUR SUIVANT ({nb_restants} restants)",
                        self.joueur_suivant, couleur=COULEURS['accent2'])
        else:
            self.bouton(f, "🗳  PASSER AU VOTE", self.afficher_vote,
                        couleur=COULEURS['vert'])

    # -------------------------------------------------------
    # JOUEUR SUIVANT
    # -------------------------------------------------------
    def joueur_suivant(self):
        self.joueur_actuel += 1
        self.afficher_tour()

    # -------------------------------------------------------
    # VOTE
    # -------------------------------------------------------
    def afficher_vote(self):
        f = self.clear()
        self.titre(f, "🗳  QUI EST L'IMPOSTEUR ?", taille=22)
        self.label(f, "Discutez entre vous, puis votez !", couleur=COULEURS['gris'])

        tk.Frame(f, bg=COULEURS['accent'], height=2, width=400).pack(pady=10)

        self.var_vote = tk.StringVar()
        for joueur in self.joueurs:
            rb = tk.Radiobutton(f, text=joueur['nom'],
                                variable=self.var_vote,
                                value=joueur['nom'],
                                font=('Courier', 13),
                                fg=COULEURS['texte'],
                                bg=COULEURS['bg'],
                                selectcolor=COULEURS['accent2'],
                                activebackground=COULEURS['bg'],
                                activeforeground=COULEURS['accent'])
            rb.pack(pady=3)

        self.bouton(f, "✅  CONFIRMER LE VOTE", self.afficher_resultat)

    # -------------------------------------------------------
    # RÉSULTAT
    # -------------------------------------------------------
    def afficher_resultat(self):
        vote = self.var_vote.get()
        if not vote:
            messagebox.showwarning("Vote manquant", "Sélectionne un joueur !")
            return

        f = self.clear()
        imposteur = next(j for j in self.joueurs if j['role'] == 'imposteur')
        mot_civil, mot_imposteur, _ = self.theme

        vote_correct = (vote == imposteur['nom'])

        if vote_correct:
            self.titre(f, "✅ BIEN JOUÉ !", couleur=COULEURS['vert'])
            self.label(f, f"Les civils ont trouvé l'imposteur !", taille=14, couleur=COULEURS['vert'])
        else:
            self.titre(f, "❌ L'IMPOSTEUR A GAGNÉ !", couleur=COULEURS['accent'])
            self.label(f, f"Vous avez voté pour {vote}, mais c'était {imposteur['nom']} !", taille=13)

        tk.Frame(f, bg=COULEURS['gris'], height=1, width=400).pack(pady=15)

        self.label(f, f"🟦 Mot des civils : « {mot_civil} »", taille=13, couleur=COULEURS['texte'])
        self.label(f, f"🟥 Mot de l'imposteur : « {mot_imposteur} »", taille=13, couleur=COULEURS['accent'])
        self.label(f, f"🕵️ L'imposteur était : {imposteur['nom']}", taille=14, couleur=COULEURS['orange'])

        tk.Frame(f, bg=COULEURS['gris'], height=1, width=400).pack(pady=15)

        self.bouton(f, "🔄  REJOUER", self.afficher_accueil, couleur=COULEURS['accent2'])
        self.bouton(f, "❌  QUITTER", self.root.quit, couleur='#333333')


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------
if __name__ == '__main__':
    root = tk.Tk()
    app = UndercoverApp(root)
    root.mainloop()