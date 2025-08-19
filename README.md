# infra-ai-self-hosted-amdryzenai
Self hosted infrastructure pour automatisation, application ia etc depuis RYZEN AI CPU/GPU/NPU modèle 
ACEMAGIC AM08 Pro AMD Ryzen 7 8845HS Mini PC

# Stack IA auto-hébergée prêt Coolify : **n8n queue-mode**, **Supabase Full**, **WAHA**, **Converter**, **Whisper**, **Ollama (CPU/AMD ROCm)**.

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

#8) Améliorations possibles

NPU Ryzen AI (Linux) : aujourd’hui, Ollama ne supporte pas le NPU (suivre l’issue publique). 
Accélération NPU possible via Ryzen AI Software + ONNX Runtime GenAI/Lemonade (serveur REST compatible). 
À évaluer si besoin d’inférence NPU. 
GitHub
ryzenai.docs.amd.com

