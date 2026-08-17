# Migration skeleton -- starting point, not a finished app

## Layout
```
your-repo/
├── agents/          <- KEEP, unchanged (copy from your existing repo)
├── core/            <- KEEP, unchanged
├── prompts/         <- KEEP, unchanged
├── tools/           <- KEEP, unchanged
├── config.py        <- KEEP, unchanged
├── api/             <- NEW (this skeleton)
│   ├── main.py
│   └── routes/
│       ├── analyze.py   (wraps FileAgent, streams progress via SSE)
│       ├── chat.py       (wraps QueryAgent)
│       └── report.py     (wraps ReportAgent)
└── frontend/        <- NEW (this skeleton)
    └── app/page.tsx  (chat UI + sidebar presets, Vercel AI SDK)
```

## To actually run this today

Backend:
```
cd your-repo
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000
```
Test it works before touching the frontend at all:
```
curl -X POST http://localhost:8000/api/analyze/stream -F "files=@some_pid.pdf"
```

Frontend:
```
cd frontend
npx create-next-app@latest . --typescript --tailwind --app  # if not already scaffolded
npm install ai lucide-react
npx shadcn@latest init   # for the polished component primitives (buttons, cards, etc.)
npm run dev
```

## Milestone order (don't try to do this all at once)

1. **Backend only.** Get `/api/analyze/stream`, `/api/chat`, `/api/report` working and
   tested via curl/Postman. This validates your existing agent code ports cleanly with
   zero frontend risk. If this milestone works, the hard part is done.
2. **Minimal chat UI.** Wire the sidebar preset buttons to pre-fill the input and hit
   `/api/chat`. Don't build streaming or the artifact panel yet -- get one round-trip
   working end to end first.
3. **Streaming.** Connect `/api/analyze/stream`'s SSE events to the chat so progress
   messages appear live, matching what your current "Agent log" expander shows.
4. **Artifact panel.** Render structured extraction results (valve tables, instrument
   lists) as an actual table/card next to the chat, not as a wall of text in a bubble --
   this is what will make the tool feel genuinely polished rather than like a chatbot
   wrapper.
5. **Auth + persistence.** Before anyone outside you touches this: real user accounts,
   a Postgres table for conversations/messages, and a tenant_id on every row. Do not
   skip this before any external test.

## What's deliberately left undone here
- Real conversation persistence (this skeleton has no database yet -- add a Postgres
  `conversations`/`messages` table before milestone 5)
- Auth (nothing here checks who's asking -- fine for solo testing, not fine for anyone else)
- The "route chat message to the right agent automatically" logic -- this skeleton uses
  explicit preset buttons instead, which is more reliable to build first. A general
  intent classifier can come later once the explicit flows all work.
