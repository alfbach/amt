# VMware → OpenShift Virtualization Migrations-Analyse

Diese App analysiert RVTools-Exporte (XLSX/CSV) und erstellt Migrationsempfehlungen sowie einen Migrationsplan für den Wechsel von VMware vSphere zu Red Hat OpenShift Virtualization (inkl. Migration Toolkit for Virtualization, MTV).

## Repository auf GitHub anlegen und pushen

Das Projekt ist lokal als Git-Repo eingerichtet. So legen Sie ein neues Repository auf GitHub an und pushen den Code:

1. Auf [GitHub](https://github.com/new) ein **neues Repository** erstellen (z. B. `vmware-to-openshift-migration`), **ohne** README, .gitignore oder License zu initialisieren.
2. Im Projektordner den Remote hinzufügen und pushen (ersetzt `IHR-USERNAME` und ggf. den Repo-Namen):

   ```bash
   cd /Users/abach/vmware-to-openshift-migration
   git remote add origin https://github.com/IHR-USERNAME/vmware-to-openshift-migration.git
   git branch -M main
   git push -u origin main
   ```

   Mit SSH:

   ```bash
   git remote add origin git@github.com:IHR-USERNAME/vmware-to-openshift-migration.git
   git push -u origin main
   ```

## Voraussetzungen

- Python 3.9+
- RVTools-Export: **File → Export all to Excel** (oder CSV) in RVTools

## Installation

```bash
cd vmware-to-openshift-migration
pip install -r requirements.txt
```

## Start

**Wichtig:** Der Befehl muss im Projektordner `vmware-to-openshift-migration` ausgeführt werden.

```bash
cd vmware-to-openshift-migration
streamlit run app.py
```

Oder von überall mit vollem Pfad:

```bash
streamlit run /pfad/zu/vmware-to-openshift-migration/app.py
```

Alternativ das Start-Skript nutzen:

```bash
./run.sh
# oder: bash run.sh
```

Im Browser öffnet sich die Oberfläche. Dort können Sie:

1. **RVTools-Datei hochladen** (`.xlsx` oder `.csv` von vInfo/vVM)
2. **Übersicht** über VMs, Cluster und Ressourcen einsehen
3. **Empfehlungen** zur OpenShift-Virtualization-Kompatibilität abrufen
4. **Migrationsplan** (Phasen, Reihenfolge, Risiken) herunterladen

## Unterstützte RVTools-Tabs

- **vInfo** (primär): VM-Name, Powerstate, CPUs, Memory, Provisioned/In Use, Cluster, Host, OS, UUID
- Optional: vDisk, vNic, vDatastore für detailliertere Empfehlungen

## Hinweise

- Speicherangaben in RVTools sind in **MiB** (nicht MB).
- Für Warm-Migration wird VMware Tools und ggf. VDDK vorbereitet.
- Der Plan berücksichtigt MTV (Migration Toolkit for Virtualization) und Cold/Warm-Migration.
