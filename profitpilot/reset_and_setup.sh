#!/usr/bin/env bash
# reset_and_setup.sh
# Use with caution — will remove files in current directory except .git and .gitignore
set -euo pipefail
echo "🚀 Resetting repository structure..."

# === CONFIG ===
REPO_URL="${1:-YOUR_GITHUB_REPO_URL}"
BRANCH="${2:-main}"
PROJECT_NAME="profitpilotai"

if [ -z "$REPO_URL" ] || [ "$REPO_URL" = "YOUR_GITHUB_REPO_URL" ]; then
  echo "⚠️  Missing REPO_URL. Usage: ./reset_and_setup.sh <repo_url> [branch]"
  exit 1
fi

echo "Cleaning files (preserving .git and .gitignore)..."
shopt -s extglob
rm -rf !(.git|.gitignore)

echo "Creating project layout..."
mkdir -p "$PROJECT_NAME/backend"
mkdir -p "$PROJECT_NAME/frontend/src/components"
mkdir -p "$PROJECT_NAME/backend/routes"
mkdir -p "$PROJECT_NAME/backend/models"

# placeholder files
cat > "$PROJECT_NAME/backend/main.py" <<'PY'
# placeholder
print("Replace with real backend/main.py")
PY

cat > "$PROJECT_NAME/frontend/src/index.jsx" <<'JS'
/* placeholder */
console.log("replace with frontend index.jsx");
JS

git add .
git commit -m "Reset repo skeleton"
git remote add origin "$REPO_URL" || true
git push -u origin "$BRANCH" -f
echo "✅ Done."
