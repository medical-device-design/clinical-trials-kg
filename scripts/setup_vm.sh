#!/usr/bin/env bash
# One-time setup on VM .83. Creates the shared tree /srv/clinical-trials-kg ($CTKG),
# group mdkg, setgid, same layout as /srv/medical-device-kg and /srv/nih-reporter-kg.
set -euo pipefail
CTKG=/srv/clinical-trials-kg
sudo mkdir -p "$CTKG"/{repo,downloads,out,logs}
sudo chgrp -R mdkg "$CTKG"
sudo chmod -R g+rwX "$CTKG"
sudo find "$CTKG" -type d -exec chmod g+s {} +
echo "export CTKG=$CTKG" >> ~/.bashrc
echo "Created $CTKG. Copy or clone the repo into $CTKG/repo, then: python3 tests/test_pipeline.py"
command -v riot >/dev/null || echo "NOTE: riot not on PATH (Jena 5.2.0 is installed for the device KG, add its bin to PATH)"
command -v shacl >/dev/null || echo "NOTE: shacl not on PATH (same Jena bin folder)"
