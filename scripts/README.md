## A self-aware homelab wizard 🧙‍♂️

A series of scripts to improve my QoL while I'm configuring my development homelab.

### pihole_sync_from_traefik.py

Automatically scans Traefik-enabled containers and syncs their subdomains into Pi-hole v6 via API.

No more manual DNS entries. Add a service, get a domain. Magic ✨

**How to use**
1. Setup your .env file
```bash
PIHOLE_BASE_URL=your-pihole-ip-addr
PIHOLE_USER=pihole-user
PIHOLE_PASSWORD=pihole-psw
TARGET_IP=homelab-ip
VERIFY_TLS=True
DOMAIN_SUFFIX=example.com
```

2. Create a python virtual env or activate devbox
```bash
devbox shell
```

3. Execute the script
```bash
python pihole_sync_from_traefik.py
```

Example output

```bash
Discovered 5 host(s):
  - home.lab.home
  - portainer.lab.home
  - s3.lab.home
  - s3console.lab.home
  - traefik.lab.home
Authenticated to Pi-hole API.
Skipped home.lab.home: already present.
Skipped portainer.lab.home: already present.
Skipped s3.lab.home: already present.
Skipped s3console.lab.home: already present.
Skipped traefik.lab.home: already present.
✅ Synced 0 DNS host record(s) to Pi-hole.
```