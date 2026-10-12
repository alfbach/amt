# OpenShift-Deployment — AlfsMigrationToolkit (Projekt `vma`)

Anleitung zum Bauen des Container-Images mit **Podman** und zum Deployen in das OpenShift-Projekt **`vma`**. Die App läuft als Streamlit-Service; RVTools-Uploads (XLSX/CSV, bis 200 MB) sind dafür ausgelegt.

## Voraussetzungen

- Podman (lokal) bzw. `oc` (OpenShift CLI)
- Zugang zu einem OpenShift-Cluster mit Rechten zum Anlegen/Nutzen des Projekts `vma`
- Optional: interne Image-Registry des Clusters

## 1. Image mit Podman bauen

Im Repository-Root:

```bash
podman build --format docker -t alfs-migration-toolkit:latest .
```

Lokal testen (Port 8501):

```bash
podman run --rm -p 8501:8501 alfs-migration-toolkit:latest
```

Im Browser: `http://localhost:8501` → RVTools-Datei hochladen (z. B. `sample_rvtools.csv`).

Upload-Smoke-Test ohne UI (Parser im Container):

```bash
podman run --rm -v "$(pwd)/sample_rvtools.csv:/data/sample.csv:ro,Z" \
  --entrypoint python alfs-migration-toolkit:latest \
  -c "from rvtools_parser import load_rvtools_bytes; d=open('/data/sample.csv','rb').read(); s=load_rvtools_bytes(d,'sample.csv'); print('sheets', list(s)); print('rows', len(s['vInfo']))"
```

Erwartete Ausgabe u. a.: `sheets ['vInfo']` und `rows 3`.

## 2. OpenShift-Projekt `vma`

```bash
# Einloggen
oc login --server=<API-URL> --token=<TOKEN>

# Projekt anlegen (falls noch nicht vorhanden)
oc new-project vma --display-name="VMware Migration Assessment"

# Oder bestehendes Projekt nutzen
oc project vma
```

## 3. Image in die Cluster-Registry pushen

Tag und Push gegen die interne Registry (Beispiele anpassen):

```bash
# Registry-Host ermitteln (externer Push von außerhalb des Clusters)
REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}' 2>/dev/null || true)

# Falls keine default-route: oc expose oder ImageStream-Import nutzen (siehe Alternative unten)
oc registry login

podman tag alfs-migration-toolkit:latest "${REGISTRY}/vma/alfs-migration-toolkit:latest"
podman push "${REGISTRY}/vma/alfs-migration-toolkit:latest"
```

**Alternative ohne externen Registry-Zugang** — Build im Cluster (OpenShift Build):

```bash
oc project vma
oc new-build --name=alfs-migration-toolkit --binary --strategy=docker -l app=alfs-migration-toolkit
oc start-build alfs-migration-toolkit --from-dir=. --follow
```

Das erzeugt/aktualisiert den ImageStream `alfs-migration-toolkit` in `vma`.

## 4. Manifeste anwenden

Die Manifeste liegen unter `openshift/` (Namespace `vma`):

| Datei | Inhalt |
|--------|--------|
| `imagestream.yaml` | ImageStream |
| `deployment.yaml` | Deployment, Probes, Ressourcen, `/tmp` emptyDir |
| `service.yaml` | ClusterIP Service (Port 8080 → 8501) |
| `route.yaml` | Edge-TLS-Route, Timeout 3600s, Session-Affinity |

```bash
oc project vma

# ImageStream + Deployment + Service + Route
oc apply -k openshift/

# Falls das Image noch nicht unter dem erwarteten Namen liegt, Image im Deployment setzen:
# oc set image deployment/alfs-migration-toolkit \
#   app=image-registry.openshift-image-registry.svc:5000/vma/alfs-migration-toolkit:latest
```

Status prüfen:

```bash
oc get pods,svc,route -l app=alfs-migration-toolkit -n vma
oc logs -f deploy/alfs-migration-toolkit -n vma
```

Route-URL:

```bash
oc get route alfs-migration-toolkit -n vma -o jsonpath='https://{.spec.host}{"\n"}'
```

## 5. RVTools-Upload im Cluster

1. Route-URL öffnen.
2. Auf der Analyse-Seite **Upload RVTools file** wählen.
3. Export aus RVTools: **File → Export all to Excel** (`.xlsx`) oder CSV (`vInfo`/`vVM`).
4. Nach dem Import erscheinen VM-Übersicht, Empfehlungen und Migrationsplan.

Hinweise:

- Max. Upload-Größe: **200 MB** (`STREAMLIT_SERVER_MAX_UPLOAD_SIZE` / Streamlit-Config).
- Im Container sind `enableXsrfProtection=false` und `enableCORS=false` gesetzt — sonst schlägt `st.file_uploader` mit 403/400 fehl (bekanntes Streamlit-Verhalten hinter Proxy/Docker).
- Die Route hat `haproxy.router.openshift.io/timeout: 3600s` für große Dateien und lange Sessions.
- Sticky Sessions (`balance: source`) halten Streamlit-WebSockets stabil.
- Der Parser liest Uploads aus dem Speicher (kein Tempfile nötig); `/tmp` ist trotzdem als emptyDir gemountet.

## 6. Aktualisieren / Rollback

```bash
# Neues Image bauen und pushen, dann Rollout
podman build -t alfs-migration-toolkit:latest .
podman push "${REGISTRY}/vma/alfs-migration-toolkit:latest"
oc rollout restart deployment/alfs-migration-toolkit -n vma
oc rollout status deployment/alfs-migration-toolkit -n vma
```

Oder nach Cluster-Build:

```bash
oc start-build alfs-migration-toolkit --from-dir=. --follow -n vma
oc rollout status deployment/alfs-migration-toolkit -n vma
```

## 7. Deinstallieren

```bash
oc delete -k openshift/ -n vma
# optional: BuildConfig / ImageStream-Tags behalten oder mitlöschen
oc delete bc/alfs-migration-toolkit -n vma --ignore-not-found
```

## Troubleshooting

| Symptom | Maßnahme |
|---------|----------|
| Pod `CrashLoopBackOff` / Permission denied | Image mit group-writable `/app` und `/tmp` bauen (Dockerfile); SCC `restricted-v2` belassen |
| Upload schlägt fehl / Timeout | Route-Annotation Timeout prüfen; Datei &lt; 200 MB; `oc logs` auf Parser-Fehler prüfen |
| Leere Seite / WebSocket-Fehler | Route TLS edge + sticky `source`; Browser-Hard-Reload |
| ImagePullBackOff | ImageStream-Tag und `image:` im Deployment prüfen; `oc describe pod …` |
| Health-Probe fail | App braucht ~10–30 s Start; Probes in `deployment.yaml` bereits angepasst |

Lokal ohne OpenShift weiter nutzen:

```bash
podman run --rm -p 8501:8501 alfs-migration-toolkit:latest
```
