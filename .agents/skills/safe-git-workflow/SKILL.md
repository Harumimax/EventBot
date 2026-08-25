---
name: safe-git-workflow
description: Use this when a task will modify code in a Git repository. Trigger before implementing changes, especially when the user works with AI agents and wants safe, reviewable edits.
---

Always treat Git as the safety layer.

Workflow:
1. Before making meaningful edits, check repository state:
   - git status
   - optionally git diff --stat
2. If there are unrelated uncommitted changes, warn the user before proceeding.
3. Prefer minimal, scoped edits.
4. Never rewrite history unless the user explicitly asks.
5. Never run destructive Git commands automatically.
6. After code changes, recommend:
   - git diff
   - git status
7. Suggest a commit message in imperative style.
8. Do not touch files outside the requested scope.
9. If sandbox restrictions prevent Git actions, explain that clearly and continue with code changes only.