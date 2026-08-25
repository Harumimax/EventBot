---
name: review-before-apply
description: Use this when the task is non-trivial and the user wants controlled changes. Trigger for multi-file edits, schema changes, refactors, external API work, or any task where review should happen before broad edits.
---

For non-trivial work, slow down and make the process reviewable.

Required behavior:
1. Start with:
   - goal
   - assumptions
   - plan
2. Then list files to be changed.
3. Explain risks briefly:
   - migration risk
   - auth/authorization risk
   - data integrity risk
   - external API risk
4. Only then implement.
5. After implementation, provide:
   - concise summary
   - exact verification commands
   - rollback idea if relevant
6. Prefer one feature slice over a broad rewrite.
7. If the user asks for “everything at once”, still split into the smallest safe implementation slice.