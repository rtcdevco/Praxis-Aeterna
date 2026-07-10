#!/usr/bin/env bash
# Create a client-branded fork: ./deploy/scripts/reskin.sh acme-corp
set -e
CLIENT="${1:?usage: reskin.sh <client-name>}"
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$SRC/../${CLIENT}-os"

echo "Creating reskinned version for: $CLIENT"
mkdir -p "$DEST"
cp -r "$SRC"/{config,core,face,voice,vault_connector,skills,deploy,requirements.txt,requirements-voice.txt,pyproject.toml,deploy.sh,Dockerfile,.dockerignore,.env.example,.gitignore} "$DEST/"

mkdir -p "$DEST"/vault/{00-inbox,01-daily,02-projects,03-clients,04-knowledge,05-templates,06-archive}
cp "$SRC"/vault/05-templates/daily.md "$DEST"/vault/05-templates/ 2>/dev/null || true
for folder in 00-inbox 01-daily 02-projects 03-clients 04-knowledge 06-archive; do
  touch "$DEST/vault/$folder/.gitkeep"
done

# Rebrand
TITLE="$(echo "$CLIENT" | tr '-' ' ' | awk '{for(i=1;i<=NF;i++)$i=toupper(substr($i,1,1))substr($i,2)}1')"
UPPER_TITLE="$(echo "$TITLE" | tr '[:lower:]' '[:upper:]')"
sed -i.bak "s/Fable 5 OS/${TITLE} OS/g; s/V\\.A\\.U\\.L\\.T\\./${UPPER_TITLE} HUD/g" \
  "$DEST/face/static/index.html" "$DEST/face/main.py"
rm -f "$DEST/face/static/index.html.bak" "$DEST/face/main.py.bak"

mkdir -p "$DEST/skills/${CLIENT}"
cat > "$DEST/skills/${CLIENT}/SKILL.md" <<SKILL
---
keywords: [${CLIENT}]
priority: 0
---
# ${TITLE} Skill

## Identity
Client-specific skill for ${TITLE}.
SKILL

cat > "$DEST/README.md" <<README
# ${TITLE} OS

Client deployment of Fable 5 OS. Run \`./deploy.sh local\` (see the main
Fable 5 OS repo for full setup and deploy-mode docs).
README

cd "$DEST" && git init -q
echo "✓ ${CLIENT} OS created at $DEST"
