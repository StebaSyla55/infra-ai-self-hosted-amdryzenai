# README.md

Stack IA auto-hébergée **prête Coolify** : **n8n (queue-mode)**, **Supabase (Full)**, **WAHA**, **Converter**, **Whisper**, **Ollama (CPU / AMD ROCm)**.
Sécurité & secrets intégrés (init auto + option de chiffrement au repos).

---

## Sommaire

1. [Arborescence](#arborescence)
2. [Pré-requis hôte](#1-pré-requis-hôte)

   1. [AMD ROCm (GPU AMD)](#11-amd-rocm--gpu-amd)
3. [Variables d’environnement (.env)](#2-variables-denvironnement-env)
4. [Déploiement via Coolify](#3-déploiement-via-coolify)
5. [Vérifications (healthy)](#4-vérifications-healthy)
6. [Sauvegardes](#5-sauvegardes)
7. [Intégration WAHA ↔ n8n](#6-intégration-waha--n8n)
8. [Notes Supabase](#7-notes-supabase)
9. [Améliorations possibles](#8-améliorations-possibles)
10. [Sécurisation supplémentaire (secrets au repos)](#9-sécurisation-supplémentaire-secrets-au-repos)
11. [Dépannage](#10-dépannage)

---

## Arborescence

```
infra-ai-self-hosted-amdryzenai/
├─ docker-compose.yml
├─ .env.example
├─ README.md
├─ secrets/
│  ├─ Dockerfile
│  └─ init_secrets.py
├─ converter/
│  ├─ Dockerfile
│  └─ api.py
└─ whisper/
   ├─ Dockerfile
   ├─ requirements.txt
   └─ transcribe_all.py
```

> Le dossier `supabase/volumes/*` est attendu si vous utilisez Storage/Functions/Kong custom (copie du répertoire `docker/` officiel Supabase).

---

## 1) Pré-requis hôte

```bash
# Dossiers de travail (droits n8n = UID 1000)
sudo mkdir -p /srv/{n8n_data,n8n_backup,shared,waha_data} \
               /srv/shared/{audio_in,audio_out}
sudo chown -R 1000:1000 /srv/n8n_data /srv/n8n_backup /srv/shared
sudo chmod -R u+rwX,g+rwX /srv/shared
```

### 1.1 (AMD ROCm) — GPU AMD

Vérifier que les devices existent :

```bash
ls -l /dev/kfd /dev/dri
```

> Les conteneurs ROCm doivent **monter `/dev/kfd` et `/dev/dri`** (déjà géré dans le compose).

Installation rapide ROCm (Ubuntu 22.04) :

```bash
# Clé + dépôt
sudo mkdir -p /etc/apt/keyrings
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | gpg --dearmor | \
  sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.4.3 jammy main" | \
  sudo tee /etc/apt/sources.list.d/rocm.list
echo -e 'Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600' | \
  sudo tee /etc/apt/preferences.d/rocm-pin-600
sudo apt update && sudo apt install -y rocm

# (optionnel) libs
echo -e "/opt/rocm/lib\n/opt/rocm/lib64" | sudo tee -a /etc/ld.so.conf.d/rocm.conf
sudo ldconfig

# Accès utilisateurs docker (si besoin)
sudo usermod -aG video,render $USER
# ou udev:
echo 'KERNEL=="kfd", MODE="0666"
SUBSYSTEM=="drm", KERNEL=="renderD*", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/70-amdgpu.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# Reboot + vérifs
sudo reboot
sudo apt install -y rocminfo
rocminfo
```

> **Secure Boot** : signer `amdgpu-dkms` ou désactiver Secure Boot si le module ne se charge pas.

---

## 2) Variables d’environnement (.env)

Dans **Coolify → Environment**, **collez** tout le contenu de **`.env.example`**. # Dans le développer view

* Laissez **VIDES** toutes les variables marquées *(auto-gen)* : elles sont créées au **1er déploiement** par le service **`secrets-init`** puis **sauvegardées** (cf. §9).
* `N8N_ENCRYPTION_KEY` : laissez vide (auto-gen) **ou** générez-la vous-même avec `openssl rand -hex 32`.
* **Supabase** : si vides, `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY` sont **auto-générées** (`ANON/SERVICE` = JWT HS256 avec `role=anon` / `role=service_role`).

---

## 3) Déploiement via Coolify

1. **Add Resource → Docker Compose (Git)**

   * Repo : `https://github.com/StebaSyla55/infra-ai-self-hosted-amdryzenai`
   * Branche : `main`
   * Fichier : `docker-compose.yml`
   * Onglet **Environment** : collez `.env.example` puis ajustez vos domaines/URLs.
2. **Accès public** (Cloudflared/Traefik déjà en place)

   * `n8n.domaine.com` → service `n8n-api:5678`
   * `waha.domaine.com` → service `waha:3000`
   * `supabase.domaine.com` → service `kong:8000`
   * `studio.domaine.com` → service `studio:3000`
     → Protégez `n8n`, `waha`, `studio` via **Cloudflare Access**.
3. **Ollama (GPU/CPU)**

   * **Par défaut** : le compose démarre **Ollama ROCm** (AMD).
   * **Basculer en CPU** : remplacer l’image `ollama/ollama:rocm` par `ollama/ollama:latest` et retirer `devices:`.
   * **Modèles** : renseignez `OLLAMA_MODELS_TO_PULL` (ex : `llama3.2:3b,phi3:3.8b`) pour les pré-tirer à l’init, sinon ils seront téléchargés au **premier appel**.

> **Premier déploiement** : `secrets-init` génère toutes les clés manquantes, les écrit dans `/srv/secrets` (cf. §9), (optionnel) les pousse vers l’UI Coolify (si `COOLIFY_API_*` sont définies), puis déclenche un **redémarrage** de la ressource. Le second lancement démarre toute la stack **avec** les secrets.

---

## 4) Vérifications (healthy)

```bash
docker compose ps
docker compose logs -f n8n-api n8n-worker waha kong
curl -sf http://n8n-api:5678/ | head -n1
redis-cli -h redis-n8n -a "$REDIS_PASSWORD" PING
psql -h db -U supabase_admin -d ${POSTGRES_DB} -p ${POSTGRES_PORT} -c '\l'
```

* **n8n queue-mode** : `n8n-worker` consomme la file Redis (`EXECUTIONS_MODE=queue` + `QUEUE_BULL_*`).
* **WAHA** : accès `/swagger`; webhook global → `http://n8n-api:5678${WAHA_HOOK_URL_PATH}` (auth : `X-Api-Key: ${WAHA_API_KEY}`).
* **Supabase** : `kong` expose l’API publique ; `studio` est l’UI d’admin.

**Vérifier Ollama GPU** :

```bash
docker compose logs -f ollama ollama-init
docker exec -it ollama ollama run llama3.2:3b "Hello"
```

Logs attendus : utilisation de **HIP/ROCm**; réponse rapide.

---

## 5) Sauvegardes

* **n8n-exporter** : export des **workflows** & **credentials** toutes **5 min** → `/srv/n8n_backup/{workflows,credentials}`.
* **pg-backup** : `pg_dump` **horaire**, rétention **14 jours** → `/srv/n8n_backup/pgdump`.
* **Supabase (fichiers)** : volumes dans `./supabase/volumes/*` (storage, functions, logs).
* **Secrets** : voir §9 (coffre chiffré `/srv/secrets.enc` + vue claire `/srv/secrets`).

---

## 6) Intégration WAHA ↔ n8n

* WAHA envoie les events (`message`) vers `http://n8n-api:5678${WAHA_HOOK_URL_PATH}`.
* Dans n8n, créez un **Webhook** correspondant ; répondez via l’API WAHA avec `X-Api-Key: ${WAHA_API_KEY}`.

---

## 7) Notes Supabase

* Le compose embarque l’architecture **Self-Hosting with Docker** : Kong (gateway), Auth (GoTrue), REST (PostgREST), Realtime, Storage (+ Imgproxy), Studio, Analytics (Logflare + Vector), Pooler (Supavisor), Meta, Functions (Edge Runtime).
* Épinglez/actualisez les **tags d’images** selon vos contraintes et suivez les **release notes**.

---

## 8) Améliorations possibles

* **NPU Ryzen AI (Linux)** : non pris en charge par **Ollama** actuellement.
  Alternatives explorables : **Ryzen AI Software + ONNX Runtime GenAI** (service REST interne) ou **Lemonade Server** (OpenAI-compatible). À évaluer selon le besoin d’inférence NPU.

---

## 9) Sécurisation supplémentaire (secrets au repos)

Chiffrer `/srv/secrets` avec **gocryptfs** (bind-mount chiffré par mot de passe) :

```bash
# 1) Installer
sudo apt update && sudo apt install -y gocryptfs

# 2) Dossiers chiffré/clair
sudo mkdir -p /srv/secrets.enc /srv/secrets
sudo chown -R root:root /srv/secrets.enc /srv/secrets
sudo chmod 700 /srv/secrets.enc /srv/secrets

# 3) Mot de passe (sauvegarde offline impérative)
sudo bash -lc 'umask 077; openssl rand -base64 48 > /root/.secrets-pass'

# 4) Init + montage
sudo gocryptfs -init /srv/secrets.enc
sudo gocryptfs --passfile /root/.secrets-pass /srv/secrets.enc /srv/secrets

# 5) (Optionnel) fstab
echo 'gocryptfs#/srv/secrets.enc /srv/secrets fuse rw,nosuid,nodev,allow_other,_netdev,passfile=/root/.secrets-pass 0 0' | sudo tee -a /etc/fstab
sudo mount -a
```

* **/srv/secrets.enc** : données **chiffrées** (à sauvegarder).
* **/srv/secrets** : vue **déchiffrée**, bind-mount du service `secrets-init`.
* Conservez une **copie offline** de `/root/.secrets-pass` (sinon **récupération impossible**).
* Seul `secrets-init` écrit dedans ; les autres services consomment les **variables d’env**.

---

## 10) Dépannage

* **Permission `/dev/kfd` refusée** : ajoutez l’utilisateur aux groupes `video,render` (ou règles `udev`), redémarrez.
* **Ollama ne tire pas les modèles** : renseignez `OLLAMA_MODELS_TO_PULL` ou lancez une première requête `ollama run …`.
* **Secrets vides après premier déploiement** : vérifiez les logs `secrets-init`. Pour push auto dans l’UI : définissez `COOLIFY_API_URL`, `COOLIFY_API_TOKEN`, `COOLIFY_RESOURCE_UUID`.
* **Changement de clés Supabase** : redémarrez **tous** les services Supabase (`kong`, `auth`, `rest`, `realtime`, `storage`, `studio`, `functions`, `analytics`, `supavisor`).
* **GPU iGPU RDNA3** : selon kernel/firmware, certaines iGPU fonctionnent partiellement ; prévoyez le **profil CPU** comme filet de sécurité si ROCm n’est pas stable.

---

**Prêt !** Déployez la stack, laissez le premier cycle générer/propager les secrets, puis vérifiez l’état Healthy et les endpoints.
