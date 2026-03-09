import tkinter as tk
from tkinter import messagebox
import random
import os
import time
import threading
import cv2
from PIL import Image, ImageTk

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
DATA_DIR = r"C:\Users\julio\Desktop\Pythonprog\Undercover\DATA"

COULEURS = {
    'bg':      '#0f0f1a',
    'card':    '#1a1a2e',
    'accent':  '#e94560',
    'accent2': '#0f3460',
    'texte':   '#eaeaea',
    'gris':    '#666666',
    'vert':    '#2ecc71',
    'orange':  '#f39c12',
    'noir':    '#050510',
}

# -------------------------------------------------------
# CHARGEMENT DE LA BANQUE DE DONNÉES
# -------------------------------------------------------
def charger_themes(data_dir):
    """
    Parcourt DATA_DIR, pour chaque sous-dossier (= thème) :
    - fichier commençant par 1_ → vidéo civils
    - fichier commençant par 2_ → vidéo imposteur
    Retourne un dict { nom_theme: (chemin_civil, chemin_imposteur) }
    """
    themes = {}
    if not os.path.exists(data_dir):
        return themes
    for dossier in os.listdir(data_dir):
        chemin_dossier = os.path.join(data_dir, dossier)
        if not os.path.isdir(chemin_dossier):
            continue
        video_civil     = None
        video_imposteur = None
        for fichier in os.listdir(chemin_dossier):
            chemin_fichier = os.path.join(chemin_dossier, fichier)
            if fichier.startswith('1_'):
                video_civil = chemin_fichier
            elif fichier.startswith('2_'):
                video_imposteur = chemin_fichier
        if video_civil and video_imposteur:
            themes[dossier] = (video_civil, video_imposteur)
    return themes


# -------------------------------------------------------
# LECTEUR VIDÉO DANS TKINTER
# -------------------------------------------------------
class LecteurVideo:
    """Lit une vidéo MP4 dans un label Tkinter."""

    def __init__(self, parent, chemin, largeur=500, hauteur=300, callback_fin=None):
        self.parent       = parent
        self.chemin       = chemin
        self.largeur      = largeur
        self.hauteur      = hauteur
        self.callback_fin = callback_fin
        self.actif        = True

        self.label = tk.Label(parent, bg=COULEURS['bg'])
        self.label.pack(pady=10)

        self.cap = cv2.VideoCapture(chemin)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
        self.delai = int(1000 / self.fps)

        self.lire_frame()

    def lire_frame(self):
        if not self.actif:
            return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (self.largeur, self.hauteur))
            img   = ImageTk.PhotoImage(Image.fromarray(frame))
            self.label.configure(image=img)
            self.label.image = img
            self.parent.after(self.delai, self.lire_frame)
        else:
            # Vidéo terminée : on rebobine et on relance (loop)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.parent.after(self.delai, self.lire_frame)

    def get_duree_secondes(self):
        nb_frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        return nb_frames / self.fps if self.fps > 0 else 10

    def stop(self):
        self.actif = False
        self.cap.release()


# -------------------------------------------------------
# APPLICATION PRINCIPALE
# -------------------------------------------------------
class UndercoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🕵️  UNDERCOVER VIDÉO")
        self.root.configure(bg=COULEURS['bg'])
        self.root.geometry("650x750")
        self.root.resizable(False, False)

        self.themes          = charger_themes(DATA_DIR)
        self.nb_joueurs      = 0
        self.nb_manches      = 0
        self.manche_actuelle = 1
        self.avec_mr_white   = False
        self.noms_joueurs    = []
        self.joueurs         = []
        self.joueur_actuel   = 0
        self.theme_actuel    = None
        self.lecteur         = None
        self.frame_actuel    = None

        if not self.themes:
            messagebox.showerror("Erreur", f"Aucun thème trouvé dans :\n{DATA_DIR}\n\nVérifie que le dossier existe et contient des sous-dossiers avec 1_vidéo.mp4 et 2_vidéo.mp4")

        self.afficher_accueil()

    # -------------------------------------------------------
    # UTILITAIRES UI
    # -------------------------------------------------------
    def clear(self):
        self.stop_lecteur()
        if self.frame_actuel:
            self.frame_actuel.destroy()
        self.frame_actuel = tk.Frame(self.root, bg=COULEURS['bg'])
        self.frame_actuel.pack(fill='both', expand=True, padx=30, pady=20)
        return self.frame_actuel

    def stop_lecteur(self):
        if self.lecteur:
            self.lecteur.stop()
            self.lecteur = None

    def titre(self, parent, texte, taille=26, couleur=None):
        tk.Label(parent, text=texte,
                 font=('Georgia', taille, 'bold'),
                 fg=couleur or COULEURS['accent'],
                 bg=COULEURS['bg']).pack(pady=(0, 8))

    def label(self, parent, texte, taille=12, couleur=None):
        tk.Label(parent, text=texte,
                 font=('Courier', taille),
                 fg=couleur or COULEURS['texte'],
                 bg=COULEURS['bg'],
                 wraplength=580,
                 justify='center').pack(pady=3)

    def separateur(self, parent):
        tk.Frame(parent, bg=COULEURS['accent'], height=2, width=450).pack(pady=12)

    def bouton(self, parent, texte, commande, couleur=None, taille=13):
        b = tk.Button(parent, text=texte, command=commande,
                      font=('Courier', taille, 'bold'),
                      fg='white', bg=couleur or COULEURS['accent'],
                      relief='flat', cursor='hand2',
                      padx=20, pady=10, bd=0,
                      activebackground=COULEURS['accent2'],
                      activeforeground='white')
        b.pack(pady=6)
        return b

    # -------------------------------------------------------
    # ÉCRAN ACCUEIL
    # -------------------------------------------------------
    def afficher_accueil(self):
        f = self.clear()

        tk.Label(f, text="🕵️", font=('Arial', 55), bg=COULEURS['bg']).pack(pady=5)
        self.titre(f, "UNDERCOVER VIDÉO", taille=30)
        self.label(f, f"{len(self.themes)} thème(s) disponible(s)", couleur=COULEURS['gris'])
        self.separateur(f)

        # Grille de config
        grid = tk.Frame(f, bg=COULEURS['bg'])
        grid.pack(pady=5)

        def ligne_config(label_txt, from_, to_, row):
            tk.Label(grid, text=label_txt, font=('Courier', 12),
                     fg=COULEURS['texte'], bg=COULEURS['bg']).grid(row=row, column=0, sticky='e', padx=10, pady=6)
            spin = tk.Spinbox(grid, from_=from_, to=to_, width=4,
                              font=('Courier', 16, 'bold'),
                              justify='center',
                              bg=COULEURS['card'], fg=COULEURS['accent'],
                              buttonbackground=COULEURS['accent2'])
            spin.grid(row=row, column=1, padx=10)
            return spin

        self.spin_joueurs = ligne_config("Nombre de joueurs :", 3, 12, 0)
        self.spin_manches = ligne_config("Nombre de manches :", 1, 20, 1)

        # Case Mister White
        self.var_mr_white = tk.BooleanVar()
        cb = tk.Checkbutton(f, text="  Inclure un Mister White 👤",
                            variable=self.var_mr_white,
                            font=('Courier', 12),
                            fg=COULEURS['orange'], bg=COULEURS['bg'],
                            selectcolor=COULEURS['card'],
                            activebackground=COULEURS['bg'],
                            activeforeground=COULEURS['orange'])
        cb.pack(pady=8)

        self.separateur(f)
        self.bouton(f, "▶  COMMENCER", self.configurer_joueurs)

    # -------------------------------------------------------
    # SAISIE DES NOMS
    # -------------------------------------------------------
    def configurer_joueurs(self):
        try:
            self.nb_joueurs    = int(self.spin_joueurs.get())
            self.nb_manches    = int(self.spin_manches.get())
            self.avec_mr_white = self.var_mr_white.get()
        except:
            return

        f = self.clear()
        self.titre(f, f"👥 Prénoms des joueurs")

        self.entries_noms = []
        frame_noms = tk.Frame(f, bg=COULEURS['bg'])
        frame_noms.pack(pady=10)

        for i in range(self.nb_joueurs):
            e = tk.Entry(frame_noms, font=('Courier', 13),
                         bg=COULEURS['card'], fg=COULEURS['texte'],
                         insertbackground='white', relief='flat',
                         width=22, justify='center')
            e.insert(0, f"Joueur {i+1}")
            e.pack(pady=4)
            self.entries_noms.append(e)

        self.bouton(f, "✅  VALIDER", self.sauver_noms_et_lancer)

    def sauver_noms_et_lancer(self):
        self.noms_joueurs    = [e.get().strip() or f"Joueur {i+1}"
                                for i, e in enumerate(self.entries_noms)]
        self.manche_actuelle = 1
        self.lancer_manche()

    # -------------------------------------------------------
    # LANCEMENT D'UNE MANCHE
    # -------------------------------------------------------
    def lancer_manche(self):
        if not self.themes:
            messagebox.showerror("Erreur", "Aucun thème disponible !")
            return

        # Thème aléatoire
        nom_theme = random.choice(list(self.themes.keys()))
        self.theme_actuel = (nom_theme, *self.themes[nom_theme])
        # theme_actuel = (nom, chemin_civil, chemin_imposteur)

        # Rôles
        indices   = list(range(self.nb_joueurs))
        imposteur = random.choice(indices)
        mr_white  = None
        if self.avec_mr_white:
            restants = [i for i in indices if i != imposteur]
            mr_white = random.choice(restants)

        self.joueurs = []
        for i, nom in enumerate(self.noms_joueurs):
            if i == imposteur:
                role = 'imposteur'
            elif i == mr_white:
                role = 'mr_white'
            else:
                role = 'civil'
            self.joueurs.append({'nom': nom, 'role': role})

        random.shuffle(self.joueurs)
        self.joueur_actuel = 0

        # Affiche écran de transition manche
        f = self.clear()
        tk.Label(f, text="🎬", font=('Arial', 50), bg=COULEURS['bg']).pack(pady=15)
        self.titre(f, f"MANCHE  {self.manche_actuelle} / {self.nb_manches}")
        self.label(f, f"Thème secret : ???", couleur=COULEURS['gris'])
        self.separateur(f)
        self.label(f, f"{self.nb_joueurs} joueurs  •  {'Mister White actif' if self.avec_mr_white else 'Sans Mister White'}",
                   couleur=COULEURS['gris'])
        self.bouton(f, "▶  COMMENCER LES TOURS", self.afficher_tour)

    # -------------------------------------------------------
    # TOUR D'UN JOUEUR (écran de passation)
    # -------------------------------------------------------
    def afficher_tour(self):
        f = self.clear()
        joueur = self.joueurs[self.joueur_actuel]

        self.titre(f, f"📱 À toi, {joueur['nom']} !", taille=24)
        self.label(f, "Donne l'écran uniquement à ce joueur.\nLes autres ferment les yeux ! 👀",
                   couleur=COULEURS['gris'])
        self.separateur(f)
        self.bouton(f, "👁  VOIR MON INDICE", self.afficher_indice, couleur=COULEURS['accent2'])

    # -------------------------------------------------------
    # AFFICHAGE DE L'INDICE (vidéo ou compteur)
    # -------------------------------------------------------
    def afficher_indice(self):
        f = self.clear()
        joueur    = self.joueurs[self.joueur_actuel]
        role      = joueur['role']
        nom_theme, chemin_civil, chemin_imposteur = self.theme_actuel

        nb_restants = self.nb_joueurs - self.joueur_actuel - 1

        if role == 'mr_white':
            # --- MISTER WHITE : compteur = durée vidéo civils ---
            self.titre(f, "👤 Tu es MISTER WHITE", couleur=COULEURS['orange'])
            self.label(f, "Tu n'as pas d'indice.\nFais semblant de regarder quelque chose...", couleur=COULEURS['gris'])
            self.separateur(f)

            # Durée de la vidéo civils pour caler le compteur
            cap  = cv2.VideoCapture(chemin_civil)
            fps  = cap.get(cv2.CAP_PROP_FPS) or 25
            nb_f = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            duree = int(nb_f / fps) if fps > 0 else 10

            self.var_compte = tk.StringVar(value=f"⏱  {duree}s")
            lbl_compte = tk.Label(f, textvariable=self.var_compte,
                                  font=('Courier', 40, 'bold'),
                                  fg=COULEURS['orange'], bg=COULEURS['bg'])
            lbl_compte.pack(pady=20)

            self.btn_suivant = self.bouton(f,
                f"➡  JOUEUR SUIVANT ({nb_restants} restants)" if nb_restants > 0 else "🗳  PASSER AU VOTE",
                self.joueur_suivant if nb_restants > 0 else self.afficher_vote,
                couleur=COULEURS['gris'])
            self.btn_suivant.config(state='disabled')

            self._lancer_compte_a_rebours(duree, f)

        else:
            # --- CIVIL ou IMPOSTEUR : on joue la vidéo ---
            chemin = chemin_civil if role == 'civil' else chemin_imposteur

            if role == 'civil':
                self.titre(f, "🟦 Tu es CIVIL", couleur=COULEURS['accent2'])
            else:
                self.titre(f, "🟥 Tu es l'IMPOSTEUR", couleur=COULEURS['accent'])

            self.label(f, "Regarde bien la vidéo !", couleur=COULEURS['gris'])

            if os.path.exists(chemin):
                self.lecteur = LecteurVideo(f, chemin, largeur=480, hauteur=280)
            else:
                self.label(f, f"[Fichier introuvable]\n{chemin}", couleur=COULEURS['accent'])

            self.separateur(f)

            if nb_restants > 0:
                self.bouton(f, f"➡  JOUEUR SUIVANT ({nb_restants} restants)",
                            self.joueur_suivant, couleur=COULEURS['accent2'])
            else:
                self.bouton(f, "🗳  PASSER AU VOTE",
                            self.afficher_vote, couleur=COULEURS['vert'])

    def _lancer_compte_a_rebours(self, secondes, frame_ref):
        """Décrémente le compteur chaque seconde."""
        if secondes <= 0:
            self.var_compte.set("✅  Temps écoulé !")
            if hasattr(self, 'btn_suivant'):
                self.btn_suivant.config(state='normal')
            return
        self.var_compte.set(f"⏱  {secondes}s")
        self.root.after(1000, lambda: self._lancer_compte_a_rebours(secondes - 1, frame_ref))

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
        self.titre(f, "🗳  QUI EST L'IMPOSTEUR ?")
        self.label(f, "Discutez entre vous, puis votez !", couleur=COULEURS['gris'])
        self.separateur(f)

        self.var_vote = tk.StringVar()
        for joueur in self.joueurs:
            rb = tk.Radiobutton(f, text=f"  {joueur['nom']}",
                                variable=self.var_vote,
                                value=joueur['nom'],
                                font=('Courier', 13),
                                fg=COULEURS['texte'], bg=COULEURS['bg'],
                                selectcolor=COULEURS['card'],
                                activebackground=COULEURS['bg'],
                                activeforeground=COULEURS['accent'])
            rb.pack(pady=3, anchor='center')

        self.separateur(f)
        self.bouton(f, "✅  CONFIRMER LE VOTE", self.afficher_resultat)

    # -------------------------------------------------------
    # RÉSULTAT DE LA MANCHE
    # -------------------------------------------------------
    def afficher_resultat(self):
        vote = self.var_vote.get()
        if not vote:
            messagebox.showwarning("Vote manquant", "Sélectionne un joueur !")
            return

        f = self.clear()
        imposteur = next(j for j in self.joueurs if j['role'] == 'imposteur')
        mr_white  = next((j for j in self.joueurs if j['role'] == 'mr_white'), None)
        nom_theme, _, _ = self.theme_actuel

        vote_correct = (vote == imposteur['nom'])

        if vote_correct:
            self.titre(f, "✅  BIEN JOUÉ !", couleur=COULEURS['vert'])
            self.label(f, "Les civils ont trouvé l'imposteur !", taille=13, couleur=COULEURS['vert'])
        else:
            self.titre(f, "❌  L'IMPOSTEUR GAGNE !", couleur=COULEURS['accent'])
            self.label(f, f"Vous avez voté {vote}... mais c'était {imposteur['nom']} !", taille=13)

        self.separateur(f)
        self.label(f, f"🎬 Thème : « {nom_theme} »", taille=13, couleur=COULEURS['orange'])
        self.label(f, f"🟥 Imposteur : {imposteur['nom']}", taille=13, couleur=COULEURS['accent'])
        if mr_white:
            self.label(f, f"👤 Mister White : {mr_white['nom']}", taille=13, couleur=COULEURS['orange'])

        self.separateur(f)

        # Boutons selon s'il reste des manches
        manches_restantes = self.nb_manches - self.manche_actuelle

        if manches_restantes > 0:
            self.label(f, f"Manche {self.manche_actuelle}/{self.nb_manches}",
                       couleur=COULEURS['gris'])
            self.bouton(f, f"▶  MANCHE SUIVANTE ({manches_restantes} restante{'s' if manches_restantes > 1 else ''})",
                        self.manche_suivante, couleur=COULEURS['accent2'])

        self.bouton(f, "❌  QUITTER LA PARTIE", self.afficher_accueil, couleur='#333333')

    # -------------------------------------------------------
    # MANCHE SUIVANTE
    # -------------------------------------------------------
    def manche_suivante(self):
        self.manche_actuelle += 1
        self.lancer_manche()


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------
if __name__ == '__main__':
    root = tk.Tk()
    app  = UndercoverApp(root)
    root.mainloop()