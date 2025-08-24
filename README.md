# README.md

Stack IA auto-hébergée **prête Coolify** : **n8n (queue-mode)**, **Supabase (Full)**, **WAHA**, **Converter**, **Whisper**, **Ollama (CPU & AMD ROCm)**.

Sécurité & secrets intégrés (init auto + option de chiffrement au repos), **bind-mount Supabase** sur l’hôte, **double Ollama** (GPU & CPU) avec pulls séparés.

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
9. [Sécurisation supplémentaire (secrets au repos)](#8-sécurisation-supplémentaire-secrets-au-repos)  
10. [Dépannage](#9-dépannage)  
11. [Annexes : `.env.example` & `.env` (exemple rempli)](#10-annexes-envexample--env-exemple-rempli)

---

## Arborescence
```
infra-ai-suite/
├─ docker-compose.yml
├─ .env.example
├─ README.md
├─ secrets/
│  ├─ Dockerfile
│  └─ init_secrets.py
├─ converter/
│  ├─ Dockerfile
│  └─ api.py
├─ whisper/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ transcribe_all.py
└─ supabase/   # (si vous préférez en repo plutôt que sur /srv)
   └─ volumes/
      ├─ api/kong.yml
      ├─ logs/vector.yml
      ├─ pooler/pooler.exs
      ├─ functions/main/  (peut être vide au départ)
      └─ storage/        (backend fichiers)
```
> **Alternative retenue** : on monte **/srv/supabase** (bind-mount hôte) au lieu de `./supabase/volumes` — voir §3.

---

## 1) Pré-requis hôte
```bash
# Dossiers de travail (droits n8n = UID 1000)
sudo mkdir -p /srv/{n8n_data,n8n_backup,shared,waha_data} \
               /srv/shared/{audio_in,audio_out}
sudo chown -R 1000:1000 /srv/n8n_data /srv/n8n_backup /srv/shared
sudo chmod -R u+rwX,g+rwX /srv/shared

# Dossiers Supabase en bind-mount
sudo mkdir -p /srv/supabase/{api,logs,pooler,functions,storage}
sudo mkdir -p /srv/supabase/functions/main
sudo chown -R 1000:1000 /srv/supabase || true
```

### 1.1 (AMD ROCm) — GPU AMD
Vérifier que les devices existent :
```bash
ls -l /dev/kfd /dev/dri
```
> Les conteneurs ROCm montent **/dev/kfd** & **/dev/dri** (déjà géré dans le compose).

Installation rapide ROCm (Ubuntu 22.04) :
```bash
# Clé + dépôt
sudo mkdir -p /etc/apt/keyrings
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | gpg --dearmor | \
  sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.4.3 jammy main" | \
  sudo tee /etc/apt/sources.list.d/rocm.list
echo -e 'Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600' | \
  sudo tee /etc/apt/preferences.d/rocm-pin-600
sudo apt update && sudo apt install -y rocm

# (optionnel) libs
echo -e "/opt/rocm/lib
/opt/rocm/lib64" | sudo tee -a /etc/ld.so.conf.d/rocm.conf
sudo ldconfig

# Accès utilisateurs docker (si besoin)
sudo usermod -aG video,render $USER
# ou udev :
echo 'KERNEL=="kfd", MODE="0666"
SUBSYSTEM=="drm", KERNEL=="renderD*", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/70-amdgpu.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# Reboot + vérifs
sudo reboot
sudo apt install -y rocminfo
rocminfo
```
> **Secure Boot** : signer `amdgpu-dkms` ou désactiver Secure Boot si le module ne se charge pas.

---

## 2) Variables d’environnement (.env)
Dans **Coolify → Environment**, **collez** tout le contenu de **`.env.example`**.

- Laissez **VIDES** les variables marquées *(auto-gen)* : générées au **1er déploiement** par **`secrets-init`**, puis sauvegardées (cf. §9).
- `N8N_ENCRYPTION_KEY` : laissez vide (auto-gen) **ou** `openssl rand -hex 32`.
- **Supabase** : si vides, `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY` sont auto-générées (`role=anon` / `role=service_role`).

---

## 3) Déploiement via Coolify
1) **Add Resource → Docker Compose (Git)**
- Repo : `https://github.com/StebaSyla55/infra-ai-self-hosted-amdryzenai` # ou le tiens avec tes outils
- Branche : `main`
- Fichier : `docker-compose.yml`
- Onglet **Environment** : collez `.env.example` puis ajustez domaines/URLs.

2) **Accès public** (Cloudflared/Traefik déjà en place)
- `n8n.domaine.com` → service `n8n-api:5678`
- `waha.domaine.com` → service `waha:3000`
- `supabase.domaine.com` → service `kong:8000`
- `studio.domaine.com` → service `studio:3000`
→ Protégez `n8n`, `waha`, `studio` via **Cloudflare Access**.

3) **Supabase volumes en bind-mount**
- Le service **`supabase-bootstrap`** crée au besoin : `/srv/supabase/{api,logs,pooler,functions,storage}` et télécharge les fichiers par défaut (kong.yml, vector.yml, pooler.exs). Les services Supabase en dépendent.

4) **Ollama (GPU & CPU)**
- Deux services : `ollama-gpu` (**ROCm**) & `ollama-cpu` (CPU).  
- Ports externes : **11434 (GPU)**, **11435 (CPU)**.  
- Pulls séparés : `ollama-gpu-init` tire `Qwen2.5:7b-instruct,mxbai-embed-large`; `ollama-cpu-init` tire `gpt-oss:20b,mixtral:8x7b-instruct-v0.1`.
- Dans n8n (ou autre), ciblez :
  - Interne GPU : `http://ollama-gpu:11434`  
  - Interne CPU : `http://ollama-cpu:11434`  
  - (Externe : 11434/11435 si exposés)

> **API Coolify (secrets-init)** : la ressource déployée sur **domaine.com** peut pousser ses envs vers l’UI du **manager Coolify** sur **domaine.com#2** via `COOLIFY_API_URL=https://coolify.domaine.com#2/api/v1` + `COOLIFY_API_TOKEN`. Assurez-vous que le reverse‑proxy **transmet l’en-tête `Authorization`** (Nginx : `proxy_set_header Authorization $http_authorization;`).

---

## 4) Vérifications (healthy)
```bash
docker compose ps
docker compose logs -f n8n-api n8n-worker waha kong
curl -sf http://n8n-api:5678/ | head -n1
redis-cli -h redis-n8n -a "$REDIS_PASSWORD" PING
psql -h db -U supabase_admin -d ${POSTGRES_DB} -p ${POSTGRES_PORT} -c 'SELECT now();'
```
- **n8n queue-mode** : `n8n-worker` consomme Redis (`EXECUTIONS_MODE=queue` + `QUEUE_BULL_*`).
- **WAHA** : `/swagger`; webhook → `http://n8n-api:5678${WAHA_HOOK_URL_PATH}` (header `X-Api-Key: ${WAHA_API_KEY}`).
- **Supabase** : `kong` expose l’API publique ; `studio` est l’UI d’admin.

**Vérifier Ollama GPU** :
```bash
docker compose logs -f ollama-gpu ollama-gpu-init
docker exec -it ollama-gpu ollama run llama3.2:3b "Hello"
```
> Attendu : mention **HIP/ROCm** et réponse rapide.

---

## 5) Sauvegardes
- **n8n-exporter** : export **workflows/credentials** toutes **5 min** → `/srv/n8n_backup/{workflows,credentials}`.
- **pg-backup** : `pg_dump` **horaire**, rétention **14 jours** → `/srv/n8n_backup/pgdump`.
- **Supabase (fichiers)** : bind-mount `/srv/supabase` (storage, functions, configs).
- **Secrets** : voir §9 (coffre chiffré `/srv/secrets.enc` + vue claire `/srv/secrets`).

---

## 6) Intégration WAHA ↔ n8n
- WAHA envoie les events (`message`) vers `http://n8n-api:5678${WAHA_HOOK_URL_PATH}`.
- Dans n8n, créez un **Webhook** correspondant ; répondez via l’API WAHA avec `X-Api-Key: ${WAHA_API_KEY}`.

---

## 7) Notes Supabase
- Architecture **Self-Hosting with Docker** : Kong (gateway), Auth (GoTrue), REST (PostgREST), Realtime, Storage (+ Imgproxy), Studio, Analytics (Logflare + Vector), Pooler (Supavisor), Meta, Functions (Edge Runtime).
- Épinglez les **tags d’images** selon vos contraintes et suivez les **release notes**.

---

## 8) Sécurisation supplémentaire (secrets au repos)
Chiffrer `/srv/secrets` avec **gocryptfs** :
```bash
sudo apt update && sudo apt install -y gocryptfs
sudo mkdir -p /srv/secrets.enc /srv/secrets
sudo chown -R root:root /srv/secrets.enc /srv/secrets
sudo chmod 700 /srv/secrets.enc /srv/secrets
sudo bash -lc 'umask 077; openssl rand -base64 48 > /root/.secrets-pass'
sudo gocryptfs -init /srv/secrets.enc
sudo gocryptfs --passfile /root/.secrets-pass /srv/secrets.enc /srv/secrets
# (Optionnel) montage auto
echo 'gocryptfs#/srv/secrets.enc /srv/secrets fuse rw,nosuid,nodev,allow_other,_netdev,passfile=/root/.secrets-pass 0 0' | sudo tee -a /etc/fstab
sudo mount -a
```
- **/srv/secrets.enc** : données chiffrées (sauvegarder).  
- **/srv/secrets** : vue déchiffrée, bind-mount du service `secrets-init`.  
- Conservez une **copie offline** de `/root/.secrets-pass`.

---

## 9) Dépannage
- **401 Unauthenticated sur API Coolify** : vérifier le **token API** (Keys & Tokens → API tokens) et que Nginx **forwarde `Authorization`**. Tester en local : `curl http://127.0.0.1:8000/api/v1/version -H "Authorization: Bearer <token>"`.
- **Permission `/dev/kfd` refusée** : groupes `video,render` (ou règles `udev`), puis reboot.
- **Ollama ne tire pas** : vérifier les services `ollama-*-init` et la connectivité.
- **Secrets vides** : consulter les logs `secrets-init` ; pour push auto, définir `COOLIFY_API_URL`, `COOLIFY_API_TOKEN`, `COOLIFY_RESOURCE_UUID` (manager = `domaine.com#2`).

---

## 10) Annexes : `.env.example` (exemple rempli)

### 10.1 `.env.example`
```bash
##############################
# Réseau / URLs publiques
##############################
N8N_PUBLIC_URL=https://n8n.domaine.com
WAHA_PUBLIC_URL=https://waha.domaine.com
SUPABASE_PUBLIC_URL=https://supabase.domaine.com
SITE_URL=${N8N_PUBLIC_URL}
API_EXTERNAL_URL=${SUPABASE_PUBLIC_URL}

##############################
# Postgres (Supabase-flavor)
##############################
POSTGRES_DB=postgres
POSTGRES_PORT=5432
POSTGRES_PASSWORD=                     # (auto-gen)
# Compte applicatif n8n créé par db-init
N8N_DB_USER=n8n
N8N_DB_PASSWORD=                       # (auto-gen)

##############################
# n8n (queue-mode)
##############################
N8N_ENCRYPTION_KEY=                    # (auto-gen)
GENERIC_TIMEZONE=Europe/Paris
WEBHOOK_URL=${N8N_PUBLIC_URL}
N8N_EDITOR_BASE_URL=${N8N_PUBLIC_URL}
REDIS_PASSWORD=                        # (auto-gen)
QUEUE_BULL_REDIS_URL=redis://:${REDIS_PASSWORD}@redis-n8n:6379
QUEUE_BULL_PREFIX=n8n
OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=true
QUEUE_HEALTH_CHECK_ACTIVE=true
N8N_IMPORT_EXPORT_DIR=/backup
N8N_IMPORT_EXPORT_OVERWRITE=overwrite

##############################
# WAHA
##############################
WAHA_API_KEY=                          # (auto-gen)
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=               # (auto-gen)
WAHA_BASE_URL=${WAHA_PUBLIC_URL}
WAHA_HOOK_EVENTS=message
WAHA_HOOK_URL_PATH=/webhook/waha

##############################
# Converter
##############################
CONVERTER_API_KEY=                     # (auto-gen)

##############################
# Whisper (chemins hôte)
##############################
AUDIO_IN=/srv/shared/audio_in
AUDIO_OUT=/srv/shared/audio_out

##############################
# Ollama (GPU & CPU)
##############################
# Cibles par défaut pour les apps internes (n8n)
OLLAMA_HOST_GPU=http://ollama-gpu:11434
OLLAMA_HOST_CPU=http://ollama-cpu:11434
# Choix par défaut pour n8n
OLLAMA_HOST=${OLLAMA_HOST_GPU}
# Pulls séparés
OLLAMA_MODELS_TO_PULL_GPU=Qwen2.5:7b-instruct,mxbai-embed-large
OLLAMA_MODELS_TO_PULL_CPU=gpt-oss:20b,mixtral:8x7b-instruct-v0.1
# Optimisations GPU
OLLAMA_FLASH_ATTENTION_GPU=1
OLLAMA_KV_CACHE_TYPE_GPU=q8_0

##############################
# Supabase FULL
##############################
JWT_SECRET=                             # (auto-gen)
ANON_KEY=                               # (auto-gen)
SERVICE_ROLE_KEY=                       # (auto-gen)
KONG_HTTP_PORT=8000
KONG_HTTPS_PORT=8443
STUDIO_DEFAULT_ORGANIZATION=MyOrg
STUDIO_DEFAULT_PROJECT=MyProject
DISABLE_SIGNUP=false
ENABLE_EMAIL_SIGNUP=true
ENABLE_ANONYMOUS_USERS=false
ENABLE_EMAIL_AUTOCONFIRM=true
ENABLE_PHONE_SIGNUP=false
ENABLE_PHONE_AUTOCONFIRM=false
JWT_EXPIRY=3600
SECRET_KEY_BASE=                        # (auto-gen)
VAULT_ENC_KEY=                          # (auto-gen)
SMTP_ADMIN_EMAIL=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_SENDER_NAME="My App"
MAILER_URLPATHS_INVITE=/auth/v1/invite
MAILER_URLPATHS_CONFIRMATION=/auth/v1/confirm
MAILER_URLPATHS_RECOVERY=/auth/v1/recover
MAILER_URLPATHS_EMAIL_CHANGE=/auth/v1/confirm
IMGPROXY_ENABLE_WEBP_DETECTION=true
LOGFLARE_PRIVATE_ACCESS_TOKEN=
LOGFLARE_PUBLIC_ACCESS_TOKEN=
DOCKER_SOCKET_LOCATION=/var/run/docker.sock

##############################
# API Coolify (manager = domaine.com#2)
##############################
COOLIFY_API_URL=https://coolify.domaine.com/api/v1
COOLIFY_API_TOKEN=
COOLIFY_RESOURCE_UUID=
COOLIFY_RESOURCE_KIND=service
```


**Prêt !** Déployez. Au 1er run, `secrets-init` génère les clés manquantes, les écrit (et peut les pousser dans l’UI de **domaine.com#2** si `COOLIFY_*` sont renseignées), puis la stack redémarre et part en production.

