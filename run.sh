#!/usr/bin/env bash
# Start the Streamlit app from the script's directory (so app.py is found).
cd "$(dirname "$0")"
exec streamlit run app.py "$@"
