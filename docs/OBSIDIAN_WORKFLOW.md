# Obsidian Workflow
> Keeping durable project notes without adding more operator overhead

---

## Recommended Pattern

Use two layers of notes:

### 1. Per-box operational notes
Stored inside each operation:

`shared/notes/important_notes.md`

This is where agents or operators capture:
- major findings
- decision pivots
- lessons learned
- capstone-relevant observations

### 2. Vault notes
Copied into your Obsidian vault when the note is worth preserving outside the single box.

This keeps the repo as the working memory and Obsidian as the long-term memory.

---

## Suggested Vault Structure

Inside Obsidian, a clean starting structure would be:

- `IRONTHREAD/Boxes/`
- `IRONTHREAD/Architecture/`
- `IRONTHREAD/Capstone/`
- `IRONTHREAD/Research/`

Examples:
- one note per HTB box under `IRONTHREAD/Boxes/`
- strategy and system decisions under `IRONTHREAD/Architecture/`
- methodology ideas under `IRONTHREAD/Capstone/`

---

## Shipping Notes To Obsidian

Default vault path in this repo:

`~/Desktop/AllSeeing/Agent Orchestration Idea`

Use:

```bash
scripts/publish_obsidian_note.sh \
  "shared/notes/important_notes.md" \
  "~/Desktop/AllSeeing/Agent Orchestration Idea" \
  "IRONTHREAD/Boxes"
```

That will copy the note into your vault folder and keep the filename.

---

## How To Get Models To Remember

The reliable pattern is not "remember in conversation."

It is:
- define one canonical note file
- mention it in the agent workflow
- make note capture part of completion criteria

Good rule:
"When an architectural decision, unexpected pivot, or reusable lesson appears, append a short entry to `shared/notes/important_notes.md`."

This works better than relying on the model to spontaneously decide what matters across sessions.

---

## Best Next Step

Once the web-first thread is stable, add explicit note-capture instructions to:
- Planner
- WEBDIG
- ELLIOT

Planner is usually the best note owner because it sees the whole picture.
