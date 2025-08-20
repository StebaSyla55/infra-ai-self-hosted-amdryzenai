import os, json, time, secrets, string
import jwt, requests

# ---------- helpers ----------
def rand_hex(n=32):  # 32 -> 64 hex chars
    return secrets.token_hex(n)
def rand_ascii(n=32):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))
def need_gen(val: str, default_markers=("change-me", "", None)):
    if val is None: return True
    low = val.strip().lower()
    return any(m in low for m in default_markers) or low == ""

def gen_jwts(jwt_secret: str, years=10):
    now = int(time.time()); exp = now + years*365*24*3600
    anon = jwt.encode({"role":"anon","iss":"supabase","iat":now,"exp":exp}, jwt_secret, algorithm="HS256")
    srv  = jwt.encode({"role":"service_role","iss":"supabase","iat":now,"exp":exp}, jwt_secret, algorithm="HS256")
    return anon, srv

# ---------- collect current env ----------
env = {k:v for k,v in os.environ.items()}

# list des vars à couvrir (tu peux en ajouter)
plan = {
    "POSTGRES_PASSWORD": ("hex", 32),
    "N8N_ENCRYPTION_KEY": ("hex", 32),
    "N8N_DB_PASSWORD": ("hex", 24),
    "REDIS_PASSWORD": ("hex", 24),
    "CONVERTER_API_KEY": ("ascii", 48),
    "WAHA_API_KEY": ("ascii", 48),
    "WAHA_DASHBOARD_PASSWORD": ("ascii", 32),
    "SECRET_KEY_BASE": ("hex", 32),
    "VAULT_ENC_KEY": ("hex", 32),
    "JWT_SECRET": ("hex", 32),
}

generated = {}
for key, (kind, size) in plan.items():
    cur = env.get(key, "")
    if need_gen(cur):
        if kind == "hex":
            generated[key] = rand_hex(size)
        else:
            generated[key] = rand_ascii(size)

# Supabase JWT -> ANON_KEY / SERVICE_ROLE_KEY
jwt_secret = generated.get("JWT_SECRET") or env.get("JWT_SECRET", "")
if need_gen(env.get("ANON_KEY","")) or need_gen(env.get("SERVICE_ROLE_KEY","")):
    if not jwt_secret:
        jwt_secret = rand_hex(32); generated["JWT_SECRET"] = jwt_secret
    anon, srv = gen_jwts(jwt_secret)
    generated["ANON_KEY"] = anon
    generated["SERVICE_ROLE_KEY"] = srv

# Marqueur idempotence
generated["SECRETS_INIT_DONE"] = "true"

# ---------- persist on host (for backups) ----------
os.makedirs("/secrets", exist_ok=True)
env_path = "/secrets/stack.env"
json_path = "/secrets/stack.json"

# fusion: nouveaux > existants > actuels
final_env = dict(env)
final_env.update({k:v for k,v in env.items() if k in generated})
final_env.update(generated)

with open(env_path, "w") as f:
    for k in sorted(generated.keys()):
        f.write(f"{k}={generated[k]}\n")

with open(json_path, "w") as f:
    json.dump(generated, f, indent=2)

# ---------- print summary (maské) ----------
def mask(v, show=6):
    if not v: return v
    return v[:show] + "…" + v[-4:]
print("=== SECRETS INIT REPORT ===")
for k in sorted(generated.keys()):
    vv = generated[k]
    print(f"{k} = {mask(vv)}")
print(f"Wrote: {env_path} & {json_path}")

# ---------- optional: push to Coolify & restart ----------
base = os.getenv("COOLIFY_API_URL")         # ex: https://coolify.example.com/api/v1
token= os.getenv("COOLIFY_API_TOKEN")       # créer dans Keys & Tokens
uuid = os.getenv("COOLIFY_RESOURCE_UUID")   # UUID de la ressource (service/application)
kind = os.getenv("COOLIFY_RESOURCE_KIND","service") # service|application

if base and token and uuid:
    print("Pushing envs to Coolify…")
    headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"}
    data=[{"key":k,"value":v,"is_preview":False,"is_build_time":False,"is_literal":True,"is_multiline":False,"is_shown_once":False}
          for k,v in generated.items()]
    if kind == "application":
        url = f"{base}/applications/{uuid}/envs/bulk"
        restart_url = f"{base}/applications/{uuid}/restart"
    else:
        url = f"{base}/services/{uuid}/envs/bulk"
        restart_url = f"{base}/services/{uuid}/restart"

    r = requests.patch(url, headers=headers, json={"data": data}, timeout=30)
    print(f"Env bulk update status: {r.status_code} / {r.text}")
    # Redémarre la ressource pour appliquer les env dans l'UI & containers
    rr = requests.get(restart_url, headers=headers, timeout=30)
    print(f"Restart status: {rr.status_code} / {rr.text}")
else:
    print("Coolify push disabled (set COOLIFY_API_URL, COOLIFY_API_TOKEN, COOLIFY_RESOURCE_UUID to enable).")
