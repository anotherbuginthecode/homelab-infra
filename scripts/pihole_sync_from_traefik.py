#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from dotenv import load_dotenv
load_dotenv()

import requests


# ---------- Config via ENV ----------
PIHOLE_BASE_URL = os.getenv("PIHOLE_BASE_URL","")  # no /admin, no /api
PIHOLE_USER = os.getenv("PIHOLE_USER","")
PIHOLE_PASSWORD = os.getenv("PIHOLE_PASSWORD","")
TARGET_IP = os.getenv("TARGET_IP","")  # IP LAN della homelab (Traefik)
DOMAIN_SUFFIX = os.getenv("DOMAIN_SUFFIX","")  # filtra solo questi host
VERIFY_TLS = os.getenv("PIHOLE_VERIFY_TLS", "true").lower() in ("1", "true", "yes")

REQUIRED_ENV_VARS = {
    "PIHOLE_BASE_URL": PIHOLE_BASE_URL,
    "PIHOLE_PASSWORD": PIHOLE_PASSWORD,
    "TARGET_IP": TARGET_IP,
    "DOMAIN_SUFFIX": DOMAIN_SUFFIX,
}

missing_vars = [k for k, v in REQUIRED_ENV_VARS.items() if not v]
if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please create a .env file with the required variables and source it before running this script.")
    sys.exit(1)



ROUTER_RULE_PREFIX = "traefik.http.routers."
ROUTER_RULE_SUFFIX = ".rule"


@dataclass(frozen=True)
class PiholeAuth:
    sid: str
    csrf: str


def run_docker_ps() -> str:
    # Formato: id|||name|||labels
    cmd = [
        "docker", "ps",
        "--format",
        "{{.ID}}|||{{.Names}}|||{{.Labels}}"
    ]
    return subprocess.check_output(cmd, text=True)


def parse_labels(labels_str: str) -> Dict[str, str]:
    # labels_str formato: key=value,key=value,...
    labels: Dict[str, str] = {}
    if not labels_str.strip():
        return labels
    parts = labels_str.split(",")
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            labels[k.strip()] = v.strip()
    return labels


HOST_RE = re.compile(r"Host\(\s*`([^`]+)`\s*\)")
HOSTS_RE = re.compile(r"Hosts\(\s*`([^`]+)`(?:\s*,\s*`([^`]+)`)*\s*\)")


def extract_hosts_from_rule(rule: str) -> Set[str]:
    """
    Estrae host da rule tipo:
      Host(`portainer.lab.home`)
      Host(`a.lab.home`) || Host(`b.lab.home`)
      Host(`a.lab.home`,`b.lab.home`)  (a volte appare come Hosts(...) a seconda di come scrivi le rule)
    """
    hosts: Set[str] = set()

    # Match ripetuti di Host(`...`)
    for m in HOST_RE.finditer(rule):
        hosts.add(m.group(1))

    # Match eventuale Hosts(`a`,`b`) — raro, ma lo gestiamo
    if "Hosts(" in rule:
        inner = re.findall(r"`([^`]+)`", rule)
        for h in inner:
            hosts.add(h)

    return hosts


def discover_traefik_hosts(domain_suffix: str) -> Set[str]:
    out = run_docker_ps()
    results: Set[str] = set()

    for line in out.strip().splitlines():
        try:
            _cid, _name, labels_str = line.split("|||", 2)
        except ValueError:
            continue
        labels = parse_labels(labels_str)

        if labels.get("traefik.enable", "false").lower() != "true":
            continue

        # Cerca tutte le label *.rule
        for k, v in labels.items():
            if k.startswith(ROUTER_RULE_PREFIX) and k.endswith(ROUTER_RULE_SUFFIX):
                hosts = extract_hosts_from_rule(v)
                for h in hosts:
                    if h == domain_suffix or h.endswith("." + domain_suffix):
                        results.add(h)

    return results


def pihole_auth(base_url: str, password: str, verify_tls: bool) -> PiholeAuth:
    if not password:
        raise RuntimeError("PIHOLE_PASSWORD is required")

    url = base_url.rstrip("/") + "/api/auth"
    resp = requests.post(url, json={"password": password}, timeout=10, verify=verify_tls)
    resp.raise_for_status()
    data = resp.json()

    sid = data["session"].get("sid")
    csrf = data["session"].get("csrf")


    if not sid or not csrf:
        raise RuntimeError(f"Unexpected auth response: {data}")

    return PiholeAuth(sid=sid, csrf=csrf)


def pihole_put_host(base_url: str, auth: PiholeAuth, ip: str, fqdn: str, verify_tls: bool) -> None:
    """
    Pi-hole v6: PUT su /api/config/dns/hosts/<urlencoded "IP domain">
    senza body. :contentReference[oaicite:1]{index=1}
    """
    element = f"{ip} {fqdn}"
    element_enc = urllib.parse.quote(element, safe="")
    url = base_url.rstrip("/") + f"/api/config/dns/hosts/{element_enc}"

    headers = {
        "X-FTL-SID": auth.sid,
        "X-FTL-CSRF": auth.csrf,
    }
    resp = requests.put(url, headers=headers, timeout=10, verify=verify_tls)
    # Alcune build ritornano 200/201/204. Consideriamo ok qualsiasi 2xx.
    if resp.status_code // 100 != 2:

        raise RuntimeError(f"Failed PUT {fqdn}: {resp.status_code} {resp.text}")


def main() -> int:
    try:
        hosts = discover_traefik_hosts(DOMAIN_SUFFIX)
        if not hosts:
            print(f"No traefik hosts found for suffix '{DOMAIN_SUFFIX}'.")
            return 0

        print(f"Discovered {len(hosts)} host(s):")
        for h in sorted(hosts):
            print(f"  - {h}")
        

        auth = pihole_auth(PIHOLE_BASE_URL, PIHOLE_PASSWORD, VERIFY_TLS)
        print("Authenticated to Pi-hole API.")

        ok = 0
        for h in sorted(hosts):
            try:
                pihole_put_host(PIHOLE_BASE_URL, auth, TARGET_IP, h, VERIFY_TLS)
                ok += 1
            except RuntimeError as e:
                if "Item already present" in str(e):
                    print(f"Skipped {h}: already present.")
                    continue
                else:
                    raise
        print(f"✅ Synced {ok} DNS host record(s) to Pi-hole.")
        return 0

    except subprocess.CalledProcessError as e:
        print("Docker command failed. Are you running this on a host with docker installed and access to the daemon?")
        print(str(e))
        return 2
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
