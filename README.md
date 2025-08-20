# infra-ai-self-hosted-amdryzenai
Self hosted infrastructure pour automatisation, application ia etc depuis RYZEN AI CPU/GPU/NPU modèle 
ACEMAGIC AM08 Pro AMD Ryzen 7 8845HS Mini PC

# Stack IA auto-hébergée prêt Coolify : **n8n queue-mode**, **Supabase Full**, **WAHA**, **Converter**, **Whisper**, **Ollama (CPU/AMD ROCm)**.

## 0) Architecture dépot : 

infra-ai-self-hosted-amdryzenai/
├ docker-compose.yml
├.env.example  # A rentrer en Developer view dans Coolify.
├README.md
├converter/  # https://github.com/StebaSyla55/infra-n8n-converter
│  ├─ Dockerfile
│  └─ api.py            
└─ whisper/  # https://github.com/StebaSyla55/whisper_project
   ├─ Dockerfile
   ├─ requirements.txt  
   └─ transcribe_all.py 
   
## 1) Pré-requis hôte
```bash
# Dossiers de travail
sudo mkdir -p /srv/{n8n_data,n8n_backup,shared,waha_data} \
               /srv/shared/{audio_in,audio_out}
sudo chown -R 1000:1000 /srv/n8n_data /srv/n8n_backup /srv/shared
sudo chmod -R u+rwX,g+rwX /srv/shared
```
# (AMD ROCm uniquement)

Vérifier l’accès GPU pour les conteneurs:

ls -l /dev/kfd /dev/dri


# Les conteneurs ROCm doivent monter /dev/kfd et /dev/dri. 
rocm.docs.amd.com

## 2) Variables .env

Dans Coolify, collez .env.example dans Environment. (developer view copié les lignes avec infos remplacé du .env.example ;))

N8N_ENCRYPTION_KEY : générez via le bouton Generate random (ou openssl rand -hex 32).

Supabase Full : générez JWT_SECRET puis ANON_KEY (payload {"role":"anon"} HS256) & SERVICE_ROLE_KEY ({"role":"service_role"} HS256). 
Supabase

## 3) déploiement via coolify : 

#1) add ressource : git public (https://github.com/StebaSyla55/infra-ai-self-hosted-amdryzenai/main)

 Déploiement par : docker compose 

#2) Gestion cloudflared automatique prérégler puis Cloudflare acces pour les users. 
#3) Profils ollama : 


#4) Vérifications (healthy)

```bash
docker compose ps
docker compose logs -f n8n-api n8n-worker waha kong
curl -sf http://n8n-api:5678/ | head -n1
redis-cli -h redis-n8n -a "$REDIS_PASSWORD" PING
psql -h db -U supabase_admin -d ${POSTGRES_DB} -p ${POSTGRES_PORT} -c '\l'
```
n8n queue-mode : n8n-worker consomme la file Redis (EXECUTIONS_MODE=queue + QUEUE_BULL_*). 
n8n Docs

WAHA : acces /swagger et webhook global vers http://n8n-api:5678${WAHA_HOOK_URL_PATH}. Protégez avec WAHA_API_KEY. 
WAHA
GitHub

Supabase : kong sert l’API publique, studio est l’UI d’admin. 
Supabase

#5) Backups

n8n-exporter : export workflows/credentials toutes 5 min vers /srv/n8n_backup.

pg-backup : pg_dump horaire, rétention 14 jours.

#6) WAHA ↔ n8n

WAHA envoie les events (message) vers http://n8n-api:5678${WAHA_HOOK_URL_PATH}.

Dans n8n, crée un Webhook sur ce chemin; réponds via l’API WAHA (header X-Api-Key). 
WAHA

#7) Notes Supabase

Ce compose reprend les services officiels Self-Hosting with Docker. Pour rester à jour, épinglez les tags d’images et suivez les release notes. 
Supabase

# astuces : 

1) Supabase : générer JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY

Méthode rapide (officielle, via le site)

Ouvre la page “Self-Hosting with Docker” de Supabase.

Descends à Generate API keys → saisis ton JWT_SECRET → clique pour générer anon et service keys, puis copie/colle dans ton .env. 
Supabase


#8) Améliorations possibles

NPU Ryzen AI (Linux) : aujourd’hui, Ollama ne supporte pas le NPU (suivre l’issue publique). 
Accélération NPU possible via Ryzen AI Software + ONNX Runtime GenAI/Lemonade (serveur REST compatible). 
À évaluer si besoin d’inférence NPU. 
GitHub
ryzenai.docs.amd.com

#9) Config Ollama

Deux points : (A) activer le profil Compose gpu-amd, (B) vérifier l’accès GPU dans le conteneur.

A) Activer le profil dans Coolify

Option 1 — via profils Compose : dans la ressource Coolify, ajoute une variable d’environnement COMPOSE_PROFILES=gpu-amd, puis Redeploy. Docker Compose activera alors ollama-amd/ollama-init-amd au lieu de la variante CPU. 
Docker Documentation

Option 2 — si ta version de Coolify ignore les profils (bug connu en cours de résolution) : édite vite fait le compose dans Coolify →

commente ollama & ollama-init (CPU),

renomme ollama-amd → ollama et ollama-init-amd → ollama-init.
Ça force le chemin ROCm par défaut. 
GitHub

#Astuce 2 :

Installer ROCm côté hôte (Ubuntu 22.04)

Objectif : avoir le pilote amdgpu-dkms + l’espace utilisateur ROCm, puis vérifier que /dev/kfd et /dev/dri existent et sont accessibles. C’est la condition pour que le conteneur ollama:rocm voie le GPU. 
rocm.docs.amd.com

Ajouter le dépôt ROCm + clé (version du jour 6.4.3)

# clé
sudo mkdir -p /etc/apt/keyrings
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | gpg --dearmor | \
  sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null

# dépôt jammy
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.4.3 jammy main" | \
  sudo tee /etc/apt/sources.list.d/rocm.list

echo -e 'Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600' | \
  sudo tee /etc/apt/preferences.d/rocm-pin-600

sudo apt update


Installer ROCm (inclut les paquets usuels + dépendances)

sudo apt install -y rocm


Le guide “Ubuntu native installation” recommande cette méthode via apt. 
rocm.docs.amd.com

(Optionnel mais utile) : config post-install (liens libs + PATH)

echo -e "/opt/rocm/lib\n/opt/rocm/lib64" | sudo tee -a /etc/ld.so.conf.d/rocm.conf
sudo ldconfig


Étapes de “Post-installation instructions”. 
rocm.docs.amd.com

Donner les droits d’accès GPU aux utilisateurs Docker

Méthode simple (groupes video et render) :

sudo usermod -aG video,render $USER
# (déconnexion/reconnexion ou reboot ensuite)


Les docs ROCm proposent l’accès par groupes (video/render) ou via règles udev. 
rocm.docs.amd.com

Méthode udev (si tu préfères gérer globalement les droits) :

# Accès pour tous (exemple)
echo 'KERNEL=="kfd", MODE="0666"
SUBSYSTEM=="drm", KERNEL=="renderD*", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/70-amdgpu.rules

sudo udevadm control --reload-rules && sudo udevadm trigger


Les règles udev ci-dessus ouvrent /dev/kfd et les render nodes à tous (ou adapte à un groupe dédié). 
rocm.docs.amd.com

Redémarrer l’hôte

sudo reboot


Vérifier les devices et l’accès

# Doivent exister
ls -l /dev/kfd /dev/dri

# Outils de vérification (paquet rocminfo)
sudo apt install -y rocminfo
rocminfo   # affiche les agents s’ils sont supportés


/dev/kfd est l’interface compute indispensable ; /dev/dri expose les GPU (render nodes). 
rocm.docs.amd.com

Secure Boot : si activé, tu devras signer amdgpu-dkms ou désactiver Secure Boot (sinon chargement du module bloqué). 
rocm.docs.amd.com
Vérifier que Ollama utilise HIP (GPU)

Après le déploiement, regarde les logs côté Coolify (ou SSH) :

docker compose logs -f ollama ollama-init


Attendus :

ollama-init tire tes modèles (ex. llama3.2:3b).

ollama indique l’utilisation de HIP/ROCm ou mentionne un device GPU.

Ensuite, un mini test d’inférence :

docker exec -it ollama ollama run llama3.2:3b "Hello"


Si ça répond vite et que les logs d’ollama montrent le GPU, c’est tout bon.
GitHub
