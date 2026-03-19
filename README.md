# AlfsMigrationToolkit

AlfsMigrationToolkit analyzes RVTools exports (XLSX/CSV) and creates migration recommendations as well as a migration plan for the transition from VMware vSphere to OpenShift Virtualization (including Migration Toolkit for Virtualization, MTV).

## Create and Push Repository on GitHub

The project is set up locally as a Git repo. Here is how to create a new repository on GitHub and push the code:

1. Create a **new repository** on [GitHub](https://github.com/new) (e.g. `vmware-to-openshift-migration`), **without** initializing README, .gitignore, or License.
2. Add the remote and push in the project folder (replace `YOUR-USERNAME` and the repo name if needed):

   ```bash
   cd vmware-to-openshift-migration
   git remote add origin https://github.com/YOUR-USERNAME/vmware-to-openshift-migration.git
   git branch -M main
   git push -u origin main
   ```

   With SSH:

   ```bash
   git remote add origin git@github.com:YOUR-USERNAME/vmware-to-openshift-migration.git
   git push -u origin main
   ```

## Prerequisites

- Python 3.9+
- RVTools export: **File → Export all to Excel** (or CSV) in RVTools

## Installation

```bash
cd vmware-to-openshift-migration
pip install -r requirements.txt
```

## Start

**Important:** The command must be run from the `vmware-to-openshift-migration` project folder.

```bash
cd vmware-to-openshift-migration
streamlit run app.py
```

Or from anywhere with the full path:

```bash
streamlit run /path/to/vmware-to-openshift-migration/app.py
```

Alternatively, use the start script:

```bash
./run.sh
# or: bash run.sh
```

### Docker

Build and run with Docker:

```bash
docker build -t vmware-to-openshift-migration .
docker run -p 8501:8501 vmware-to-openshift-migration
```

Or with Docker Compose:

```bash
docker compose up --build
```

Then open **http://localhost:8501** in your browser.

The interface opens in your browser. You can:

1. **Upload RVTools file** (`.xlsx` or `.csv` from vInfo/vVM)
2. **View overview** of VMs, clusters, and resources
3. **Get recommendations** for OpenShift Virtualization compatibility
4. **Download migration plan** (phases, order, risks)

## Supported RVTools Tabs

- **vInfo** (primary): VM name, Powerstate, CPUs, Memory, Provisioned/In Use, Cluster, Host, OS, UUID
- Optional: vDisk, vNic, vDatastore for more detailed recommendations

## Notes

- Storage values in RVTools are in **MiB** (not MB).
- VMware Tools and optionally VDDK are prepared for warm migration.
- The plan considers MTV (Migration Toolkit for Virtualization) and cold/warm migration.
