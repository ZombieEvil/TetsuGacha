# 🌸 TetsuGacha

> *Le gacha ultime de ton serveur Discord.*

Bot Discord de collection multi-sources : pioche et revendique des personnages d'**anime**, **manga**, **films**, **séries**, **jeux vidéo** et **comics** pour animer ton serveur.

---

## ✨ Fonctionnalités

- 🎲 **Rolls aléatoires** multi-sources avec cooldown horaire
- 💖 **Système de revendication** avec bouton interactif (premier arrivé, premier servi)
- 📖 **Embeds riches** affichant le portrait + le poster de la licence d'origine
- ⭐ **5 niveaux de rareté** basés sur la popularité réelle des personnages
- 📋 **Wishlist** avec notifications DM quand un perso wishlisté est revendiqué
- 🤝 **Échanges** entre joueurs (double confirmation)
- 💔 **Divorce** pour libérer un perso et récupérer 50 % de sa valeur
- 💰 **Économie** avec monnaie, récompense quotidienne
- 🏆 **Leaderboard** du serveur
- 👥 **Auto-rôle** pour les nouveaux membres + application en masse
- 🖥 **Dashboard terminal** temps réel style hacker

---

## 📦 Installation

### Prérequis

- Python 3.10 ou plus
- Un compte Discord Developer

### Étapes

**1. Installer les dépendances**
```bash
pip install -r requirements.txt
```

**2. Créer ton bot Discord**
1. https://discord.com/developers/applications → *New Application* → choisis **TetsuGacha** (ou le nom que tu veux)
2. Onglet **Bot** → *Reset Token* → copie le token
3. Active **Privileged Gateway Intents** :
   - ✅ `SERVER MEMBERS INTENT`
   - ✅ `MESSAGE CONTENT INTENT`

**3. Inviter le bot**
Dans l'onglet **OAuth2 → URL Generator** :
- Scopes : `bot`, `applications.commands`
- Permissions : `Manage Roles` (pour l'auto-rôle), `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`, `Use External Emojis`

**4. Configurer**
Renomme `config.example.py` en `config.py` puis colle ton token Discord dans `DISCORD_TOKEN`.

Les autres clés API sont **optionnelles** :

| Source | Ce qu'elle apporte | Gratuit | Lien |
|--------|-------------------|---------|------|
| AniList | Anime / Manga | ✅ Sans clé | Actif par défaut |
| TMDB | Films / Séries / Acteurs | ✅ | https://www.themoviedb.org/settings/api |
| IGDB | Jeux vidéo | ✅ | https://dev.twitch.tv/console/apps |
| Comic Vine | Marvel / DC | ✅ | https://comicvine.gamespot.com/api/ |

> Si tu laisses une clé vide, la source est simplement ignorée. **AniList fonctionne sans clé** : tu peux démarrer avec juste le token Discord.

**5. Lancer**

Avec dashboard temps réel (recommandé) :
```bash
python bot.py
```

Mode logs classiques :
```bash
python bot.py --no-ui
```

---

## 🎮 Commandes

### Pour les joueurs

| Commande | Rôle |
|---|---|
| `/roll` | Pioche un personnage aléatoire |
| `/harem` | Affiche ta collection |
| `/harem personnage:<nom>` | Détails d'un personnage précis |
| `/wishlist add <nom>` | Ajoute à la wishlist |
| `/wishlist remove <nom>` | Retire de la wishlist |
| `/wishlist view` | Affiche la wishlist |
| `/trade <membre> <mon_perso> <son_perso>` | Propose un échange |
| `/divorce <nom>` | Libère un perso (remboursement 50 %) |
| `/profile` | Ton profil avec bouton récompense quotidienne |
| `/leaderboard` | Classement du serveur |
| `/help` | Liste complète |

### Pour les admins *(permission « Gérer le serveur »)*

| Commande | Rôle |
|---|---|
| `/config show` | Voir la configuration actuelle |
| `/config channel` | Définit le salon courant comme salon de rolls |
| `/config mode <source>` | Change la source (all, anime, movie, game, comic) |
| `/config role <rôle>` | Rôle auto-attribué aux nouveaux arrivants |
| `/config apply-role` | Applique le rôle à tous les membres actuels |

---

## 🖥 Dashboard terminal

Quand tu lances avec dashboard, ton terminal affiche en direct :
- Status du bot (uptime, latence, serveurs, utilisateurs)
- Stats live (rolls, claims, trades, divorces)
- Flux d'événements en temps réel
- Tableau des derniers claims avec rareté colorée
- Mode actif sur chaque serveur

> Utilise Windows Terminal ou iTerm2 pour un rendu optimal des couleurs.

---

## 🌐 Hébergement 24/7

- **VPS** (OVH, Hetzner, Contabo) ~5 €/mois — le plus stable
- **Raspberry Pi** si tu en as un chez toi
- **Ton PC** avec le terminal ouvert (pour les tests)

Sur VPS, utilise `screen` ou `systemd` pour que le bot reste lancé après déconnexion SSH.

---

## 🗂 Architecture

```
tetsugacha-bot/
├── bot.py
├── config.example.py     → renomme en config.py
├── requirements.txt
├── README.md
├── cogs/
│   ├── config.py         /config (admin)
│   ├── rolls.py          /roll + bouton claim
│   ├── collection.py     /harem
│   ├── wishlist.py       /wishlist add/remove/view
│   ├── trade.py          /trade + /divorce
│   ├── profile.py        /profile + /leaderboard
│   └── help.py           /help
├── utils/
│   ├── storage.py        Stockage JSON (aucune base SQL)
│   ├── api_fetchers.py   AniList, TMDB, IGDB, Comic Vine
│   ├── helpers.py        Embeds + raretés
│   └── dashboard.py      Dashboard temps réel
└── data/                 fichiers JSON créés automatiquement
    ├── users.json
    ├── claimed_characters.json
    ├── wishlists.json
    ├── guild_config.json
    ├── trades.json
    └── counters.json
```

### 💾 Stockage des données

Le bot **n'utilise pas de base SQL**. Toutes les données sont stockées dans des fichiers JSON dans le dossier `data/`.

**Avantages :**
- Aucune dépendance à installer pour la base
- Tu peux ouvrir les fichiers JSON dans un éditeur de texte pour inspecter ou corriger à la main
- Backup ultra simple : copier le dossier `data/`
- Restauration : copier-coller le dossier

**Sous le capot :**
- Écriture atomique (tempfile + rename) pour éviter la corruption
- Verrous async par fichier pour les accès concurrents
- Sauvegarde en arrière-plan toutes les 3 secondes (batch)
- Flush final garanti à la fermeture du bot

> Pour un serveur avec une activité très élevée (plusieurs claims/seconde en continu), SQLite serait plus performant. Pour un usage normal (même avec plusieurs centaines de membres), JSON fait très bien l'affaire.

---

## ⚙️ Personnalisation

Tout est dans `config.py` :
- `BOT_NAME`, `BOT_TAGLINE`, couleurs
- Cooldowns, valeurs de rareté, récompenses
- Taille max de la wishlist, monnaie de départ

---

## 🐛 Dépannage

**Les slash commands n'apparaissent pas**
→ Patiente quelques minutes ou kick+re-invite le bot. Vérifie que `applications.commands` était coché à l'invitation.

**Le bot n'attribue pas le rôle auto**
→ Le rôle du bot doit être **au-dessus** du rôle à attribuer dans la hiérarchie du serveur.

**`ModuleNotFoundError`**
→ `pip install -r requirements.txt`

**Crash au lancement**
→ Vérifie ton token Discord et que `config.py` existe.

---

## 📝 Licence

Projet libre pour usage personnel. Les personnages et images appartiennent à leurs ayants droit respectifs.
