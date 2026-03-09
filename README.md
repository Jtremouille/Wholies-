# 🕵️ Undercover Vidéo — Guide de déploiement

## Structure du projet
```
undercover_web/
├── app.py
├── requirements.txt
├── Procfile
├── static/css/style.css
└── templates/
    ├── accueil.html
    ├── lobby.html
    └── jeu.html
```

---

## ÉTAPE 1 — Uploader tes vidéos sur Cloudinary

1. Crée un compte gratuit sur https://cloudinary.com
2. Dans le dashboard, va dans **Media Library**
3. Crée des dossiers : `Nuit/`, `Plage/`, etc.
4. Upload tes vidéos :
   - `1_Braquage_nuit.mp4` → dans le dossier `Nuit`
   - `2_Braquage_nuit.mp4` → dans le dossier `Nuit`
5. Clique sur une vidéo → **Copy URL**
6. Dans `app.py`, remplace les URLs dans le dictionnaire `THEMES` :

```python
THEMES = {
    "Nuit": {
        "civil":     "https://res.cloudinary.com/TON_CLOUD_NAME/video/upload/Nuit/1_Braquage_nuit.mp4",
        "imposteur": "https://res.cloudinary.com/TON_CLOUD_NAME/video/upload/Nuit/2_Braquage_nuit.mp4",
    },
}
```

---

## ÉTAPE 2 — Déployer sur Railway (gratuit)

1. Crée un compte sur https://railway.app
2. Clique **New Project → Deploy from GitHub**
3. Push ton dossier `undercover_web/` sur GitHub d'abord :
   ```
   git init
   git add .
   git commit -m "first commit"
   git remote add origin https://github.com/TON_PSEUDO/undercover.git
   git push -u origin main
   ```
4. Dans Railway, sélectionne ton repo
5. Va dans **Variables** et ajoute :
   ```
   SECRET_KEY = une_chaine_aleatoire_longue
   ```
6. Railway détecte automatiquement le `Procfile` et lance le serveur
7. Clique sur **Generate Domain** → tu obtiens une URL publique du type :
   `https://undercover-production.up.railway.app`

---

## ÉTAPE 3 — Jouer !

- L'hôte ouvre l'URL sur son téléphone/ordi
- Il crée une partie → reçoit un code (ex: `ABCXYZ`)
- Les autres joueurs ouvrent la même URL et entrent le code
- L'hôte lance la partie

---

## Ajouter des thèmes

Dans `app.py`, ajoute simplement dans le dict `THEMES` :
```python
"Plage": {
    "civil":     "URL_cloudinary_video_civils",
    "imposteur": "URL_cloudinary_video_imposteur",
},
```
