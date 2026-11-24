#!/usr/bin/env bash
# Create the GitHub repository (if missing) and push this branch with history intact.
#
#   GITHUB_TOKEN=ghp_xxx GITHUB_OWNER=your-login ./scripts/publish.sh [repo-name]
#
# Defaults: repo name "skill-agent", public ( reviewers must be able to open it ),
# or REPO_PRIVATE=1 for a private repo. The token is only used in the push URL for
# this one command; it is never written into .git/config.
set -euo pipefail

REPO_NAME="${1:-skill-agent}"
OWNER="${GITHUB_OWNER:-}"
TOKEN="${GITHUB_TOKEN:-}"
PRIVATE_FLAG="false"
if [ "${REPO_PRIVATE:-0}" = "1" ]; then
  PRIVATE_FLAG="true"
fi

if [ -z "$TOKEN" ]; then
  cat <<'EOF'
GITHUB_TOKEN 未设置，无法创建仓库或推送。

准备步骤（一次性）：
  1. GitHub → Settings → Developer settings → Personal access tokens →
     生成一个带 "repo" 权限的 token（classic）或授予 Contents: read/write + Administration: write 的 fine-grained token。
  2. 重新执行：
       GITHUB_TOKEN=ghp_xxx GITHUB_OWNER=<你的用户名> ./scripts/publish.sh

脚本会：用 API 建仓库（已存在则跳过）→ 添加 origin → 推送 main（保留全部历史，
不改写提交、不改提交时间）。
EOF
  exit 2
fi

if [ -z "$OWNER" ]; then
  OWNER="$(curl -sf -H "Authorization: Bearer $TOKEN" https://api.github.com/user \
    | sed -n 's/.*"login": *"\([^"]*\)".*/\1/p' | head -1)"
  [ -z "$OWNER" ] && { echo "无法从 token 解析用户名，请显式设置 GITHUB_OWNER"; exit 1; }
fi

echo "owner=$OWNER repo=$REPO_NAME private=$PRIVATE_FLAG"

if curl -sf -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/$OWNER/$REPO_NAME" >/dev/null; then
  echo "仓库已存在，直接推送"
else
  curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO_NAME\",\"private\":$PRIVATE_FLAG,\"description\":\"Progressive-disclosure skill agent: discovery, prompt budget, routing eval, demo UI\"}" \
    >/dev/null
  echo "仓库已创建"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/$OWNER/$REPO_NAME.git"
else
  git remote add origin "https://github.com/$OWNER/$REPO_NAME.git"
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push "https://x-access-token:$TOKEN@github.com/$OWNER/$REPO_NAME.git" "$BRANCH:main" --tags
git branch --set-upstream-to="origin/main" "$BRANCH" >/dev/null 2>&1 || true

echo "完成：https://github.com/$OWNER/$REPO_NAME"
git --no-pager log --oneline | head -5
