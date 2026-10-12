# AlfsMigrationToolkit

AlfsMigrationToolkit analysiert RVTools-Exporte (XLSX/CSV) oder vCenter-Daten und erstellt Migrationsempfehlungen sowie einen Migrationsplan für den Übergang von VMware vSphere zu OpenShift Virtualization (inkl. Migration Toolkit for Virtualization, MTV).

## Features

- **Datenimport**: RVTools-Datei (XLSX/CSV) oder **vCenter Live-API** (pyvmomi)
- **Mehrsprachigkeit**: Englisch, Deutsch, Französisch
- **Analyse**: VM-Übersicht, Kompatibilitätsprüfung, Migrationsempfehlungen pro VM
- **Migrationsplan**: Phasen, Reihenfolge, Risiken, Download als Markdown
- **Risikoanalyse**: Globale und phasenbezogene Risiken mit Mitigation
- **Cluster Design**: Berechnung benötigter Worker-Nodes, CPU/RAM-Auslastung, Dichte- und Stromersparnis
- **ODF-Design**: OpenShift Data Foundation – Speicherkapazität und Replikationsfaktor
- **HA & Netzwerk**: Topologie-Diagramm, HA-Empfehlungen, Netzwerk-Einstellungen
- **Deploy-Prototyp**: Generierung von `install-config.yaml` und Run-Skripten für AWS, Azure, IBM Cloud, Bare Metal (inkl. Bare-Metal-Instanzen mit Kostenschätzung)

## Voraussetzungen

- Python 3.9+
- RVTools-Export: **File → Export all to Excel** (oder CSV) in RVTools  
  Oder: vCenter-Zugang für Live-Import (pyvmomi)

## Installation

```bash
cd amt
pip install -r requirements.txt
```

## Start

```bash
streamlit run app.py
```

Oder mit dem Start-Skript:

```bash
./run.sh
```

Dann **http://localhost:8501** im Browser öffnen.

## Podman & OpenShift

### Container-Image bauen (Podman)

```bash
podman build --format docker -t alfs-migration-toolkit:latest .
```

### Lokal starten

```bash
podman run --rm -p 8501:8501 alfs-migration-toolkit:latest
```

Dann **http://localhost:8501** öffnen und eine RVTools-Datei (XLSX/CSV) hochladen.

> **Hinweis:** Im Container sind `enableXsrfProtection=false` und `enableCORS=false` gesetzt.
> Ohne das schlägt der RVTools-Upload in Docker/Podman/OpenShift typischerweise mit 403/400 fehl.

### OpenShift (Projekt `vma`)

Vollständige Anleitung: **[docs/OPENSHIFT-DEPLOY.md](docs/OPENSHIFT-DEPLOY.md)**

```bash
oc new-project vma   # falls nötig
oc apply -k openshift/
# Image vorher pushen bzw.: oc start-build alfs-migration-toolkit --from-dir=. --follow
```

### Kubernetes (generisch)

```bash
kubectl apply -f k8s-deployment.yaml
```

## Ablauf

1. **Datenquelle wählen**: RVTools-Datei hochladen oder vCenter verbinden
2. **Analyse**: Übersicht VMs, Cluster, Ressourcen
3. **Empfehlungen**: OpenShift-Virtualization-Kompatibilität pro VM
4. **Konfiguration** (Sidebar): Worker-Größe, Overcommit, ODF, HA
5. **Cluster Design**: Benötigte Nodes, Einsparungen, ODF-Dimensionierung
6. **HA-Diagramm**: Topologie und Netzwerk-Empfehlungen
7. **Migrationsplan**: Phasen, Risiken, Download (.md)
8. **Deploy**: `install-config.yaml` und Skripte für OpenShift-Installation herunterladen

## Unterstützte RVTools-Tabs

- **vInfo** (primär): VM-Name, Powerstate, CPUs, Memory, Provisioned/In Use, Cluster, Host, OS, UUID
- Optional: vDisk, vNic, vDatastore für detailliertere Empfehlungen

## Hinweise

- Speicherwerte in RVTools sind in **MiB** (nicht MB).
- VMware Tools und optional VDDK werden für Warm-Migration vorbereitet.
- Der Plan berücksichtigt MTV (Migration Toolkit for Virtualization) sowie Cold- und Warm-Migration.

## GitHub-Repository erstellen und pushen

Das Projekt ist lokal als Git-Repo eingerichtet. So erstellst du ein neues Repository auf GitHub und pushst den Code:

1. **Neues Repository** auf [GitHub](https://github.com/new) anlegen (z.B. `vmware-to-openshift-migration`), **ohne** README, .gitignore oder License.
2. Remote hinzufügen und pushen (ersetze `YOUR-USERNAME` und den Repo-Namen bei Bedarf):

   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/vmware-to-openshift-migration.git
   git branch -M main
   git push -u origin main
   ```

   Mit SSH:

   ```bash
   git remote add origin git@github.com:YOUR-USERNAME/vmware-to-openshift-migration.git
   git push -u origin main
   ```
