# 양세찬 게임 온라인 버전 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a mobile-friendly multiplayer web game that digitizes "양세찬 게임" (Call My Name) — each player's assigned identity is visible to everyone except themselves, synced live across each player's own phone.

**Architecture:** A single Cloudflare Worker app built with the Claude website-builder stack (React 19 + TanStack Start, SSR), using a Cloudflare D1 database for room/player state. The frontend polls a small REST-style API (`/api/rooms/**`, TanStack server routes) every 2 seconds to stay in sync across devices. No auth, no Higgsfield SDK usage — this is a plain custom Tailwind app, not a Higgsfield-SDK surface.

**Tech Stack:** React 19, TanStack Start (file-based routes under `app/src/routes/`), Cloudflare Worker + D1 (`env.DB`), Tailwind v4, bun, deployed via the `deploy_website` MCP tool (preview environment).

## Global Constraints

- Min 2, max 8 players per room (spec default, adjustable per room at creation but clamp 2–8).
- Two content modes: `preset` (built-in difficulty-tiered name bank, default) and `custom` (players type names themselves).
- Custom mode with exactly 2 players: no shuffle — each player's typed name goes directly to the other player (cross-assignment), no pooling.
- Custom mode with 3+ players: pooled names are shuffled with derangement (no player receives the name they personally submitted).
- A player's own row must never include their `assignedName` in API responses unless that player has been marked finished (revealed).
- Never use `Math.random()` for IDs/codes/shuffling — use `crypto.randomUUID()` / `crypto.getRandomValues()` (Worker hard rule).
- D1 is shared between preview and production — migrations must be additive (`CREATE TABLE IF NOT EXISTS`), no destructive statements.
- Deploy only to `env='preview'` during this plan. Do not deploy `env='production'` unless the user explicitly asks after reviewing the preview.
- No Higgsfield (fnf) SDK, no `/api/user`, no login/logout — this app has no auth.

---

## File Structure

```
양세찬게임/
  app/                              # cloned website repo (own git history — gitignored from the outer repo)
    app.manifest.json               # set "db": true
    migrations/
      0001_rooms_and_players.sql
    src/
      lib/
        bindings.server.ts          # D1 accessor (getDb())
        room-code.server.ts         # generateRoomCode()
        derangement.ts              # randomDerangement()
        name-bank.ts                # preset name lists by difficulty
      routes/
        index.tsx                   # home screen
        create.tsx                  # room settings screen
        room/
          $roomId/
            index.tsx                # main room screen (waiting/playing/finished views)
        api/
          rooms/
            index.ts                 # POST create room
            $roomId/
              index.ts                # GET room state
              join.ts                 # POST join
              submit.ts               # POST submit candidate name
              start.ts                 # POST assign + start
              restart.ts               # POST re-assign + restart
              reveal.ts                # POST mark a player finished
  docs/superpowers/
    specs/2026-07-03-yangsechan-game-design.md
    plans/2026-07-03-yangsechan-online-game.md
  .gitignore                        # ignores app/ from the outer repo
```

---

### Task 1: 웹사이트 스캐폴딩 + DB 활성화

**Files:**
- Create (via MCP tool, not local write): the website project (returns `website_id`)
- Modify: `양세찬게임/app/app.manifest.json` (`"db": true`)
- Create: `양세찬게임/app/migrations/0001_rooms_and_players.sql`
- Create: `양세찬게임/app/src/lib/bindings.server.ts`
- Create/modify: `양세찬게임/.gitignore`

**Interfaces:**
- Produces: `getDb(): D1Database` from `bindings.server.ts`, used by every later API route task.
- Produces: `rooms` and `players` tables, used by every later task.

- [ ] **Step 1: Create the website**

Call the `create_website` MCP tool (no arguments). Record the returned `website_id` — every later `website_repo_access`/`deploy_website`/`website_db` call in this plan needs it.

- [ ] **Step 2: Get repo access and clone locally**

Call `website_repo_access` with the `website_id`. It returns a git URL + scoped token. Clone it:

```bash
git clone <returned-git-url> "/Users/donghwikim/바이브코딩/양세찬게임/app"
```

- [ ] **Step 3: Keep the outer repo clean of the nested clone**

Create `/Users/donghwikim/바이브코딩/양세찬게임/.gitignore` with:

```
app/
```

- [ ] **Step 4: Enable D1**

Open `양세찬게임/app/app.manifest.json`. Find the `"db"` field and set it to `true`, leaving every other field untouched:

```json
"db": true
```

- [ ] **Step 5: Write the schema migration**

```sql
-- 양세찬게임/app/migrations/0001_rooms_and_players.sql
CREATE TABLE IF NOT EXISTS rooms (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('preset', 'custom')),
  difficulty TEXT CHECK (difficulty IN ('easy', 'medium', 'hard')),
  max_players INTEGER NOT NULL DEFAULT 8,
  status TEXT NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'playing', 'finished')),
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY,
  room_id TEXT NOT NULL REFERENCES rooms(id),
  nickname TEXT NOT NULL,
  submitted_text TEXT,
  assigned_name TEXT,
  is_finished INTEGER NOT NULL DEFAULT 0,
  joined_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_players_room_id ON players(room_id);
```

- [ ] **Step 6: Write the D1 binding accessor**

```ts
// 양세찬게임/app/src/lib/bindings.server.ts
import { env } from 'cloudflare:workers'

export function getDb(): D1Database {
  const db = (env as unknown as { DB?: D1Database }).DB
  if (!db) {
    throw new Error('D1 database binding (DB) is not configured. Enable "db": true in app.manifest.json.')
  }
  return db
}
```

- [ ] **Step 7: Commit and push**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add app.manifest.json migrations/0001_rooms_and_players.sql src/lib/bindings.server.ts
git commit -m "Enable D1 and add rooms/players schema"
git push
```

- [ ] **Step 8: Deploy preview and verify the schema applied**

Call `deploy_website` with `website_id` and `env='preview'`. Expect a successful build with a preview URL.

Then call `website_db` with `website_id`, `operation='tables'`. Expect `rooms` and `players` to be listed.

---

### Task 2: 방 생성 + 참가 API + 이름 뱅크

**Files:**
- Create: `양세찬게임/app/src/lib/room-code.server.ts`
- Create: `양세찬게임/app/src/lib/name-bank.ts`
- Create: `양세찬게임/app/src/routes/api/rooms/index.ts`
- Create: `양세찬게임/app/src/routes/api/rooms/$roomId/join.ts`

**Interfaces:**
- Consumes: `getDb()` from Task 1.
- Produces: `generateRoomCode(): string`, `NAME_BANK: Record<'easy'|'medium'|'hard', string[]>` — used by Task 4's `start`/`restart` handlers.
- Produces: `POST /api/rooms` → `{ roomId: string }`; `POST /api/rooms/:roomId/join` → `{ playerId: string }` — used by the frontend in Tasks 6–7.

- [ ] **Step 1: Room code generator**

```ts
// 양세찬게임/app/src/lib/room-code.server.ts
const ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789' // no 0/O/1/I to avoid confusion

export function generateRoomCode(length = 6): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  let code = ''
  for (let i = 0; i < length; i++) {
    code += ALPHABET[bytes[i] % ALPHABET.length]
  }
  return code
}
```

- [ ] **Step 2: Preset name bank**

```ts
// 양세찬게임/app/src/lib/name-bank.ts
export type Difficulty = 'easy' | 'medium' | 'hard'

export const NAME_BANK: Record<Difficulty, string[]> = {
  easy: [
    '아이유', '손흥민', '세종대왕', '이순신', '유재석', '박명수', '김연아', '봉준호',
    '임영웅', '뽀로로', '크롱', '라이언', '펭수', '짱구', '스폰지밥', '도라에몽',
    '심청이', '흥부', '놀부', '콩쥐', '홍길동', '신사임당', '광개토대왕', '안중근',
    '유관순', '강감찬', '정국', '지수', '미키마우스', '헬로키티',
  ],
  medium: [
    '지석진', '김종국', '하하', '전소민', '양세찬', '송지효', '유병재', '장도연',
    '이용진', '홍진경', '붐', '서장훈', '이수근', '양세형', '신동엽', '김구라',
    '전현무', '강호동', '김희철', '은지원', '이광수', '송은이', '김숙', '박나래',
    '조세호', '이영자', '성시경', '규현', '데프콘', '안영미',
  ],
  hard: [
    '강림도령', '해원맥', '이덕춘', '유미', '응이', '조석', '장그래', '박새로이',
    '강백호', '서태웅', '몽키디루피', '우즈마키나루토', '봉미선', '기영이', '기철이',
    '히나타쇼요', '카마도탄지로', '아리', '티모', '디바', '짐레이너', '뮤츠',
    '루디브리지', '백두산', '라이젤', '진모리', '클레', '피카츄친구라이츄', '몬스터볼',
    '슬라임',
  ],
}

export function drawUniqueNames(difficulty: Difficulty, count: number): string[] {
  const pool = [...NAME_BANK[difficulty]]
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(secureRandom() * (i + 1))
    ;[pool[i], pool[j]] = [pool[j], pool[i]]
  }
  return pool.slice(0, count)
}

function secureRandom(): number {
  const buf = new Uint32Array(1)
  crypto.getRandomValues(buf)
  return buf[0] / 0xffffffff
}
```

- [ ] **Step 3: Create-room route**

```ts
// 양세찬게임/app/src/routes/api/rooms/index.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'
import { generateRoomCode } from '~/lib/room-code.server'
import { NAME_BANK, type Difficulty } from '~/lib/name-bank'

export const Route = createFileRoute('/api/rooms/')({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const body = await request.json().catch(() => null) as {
          mode?: string
          difficulty?: string
          maxPlayers?: number
        } | null

        const mode = body?.mode
        if (mode !== 'preset' && mode !== 'custom') {
          return Response.json({ ok: false, error: 'invalid_mode' }, { status: 400 })
        }

        let difficulty: Difficulty | null = null
        if (mode === 'preset') {
          if (body?.difficulty !== 'easy' && body?.difficulty !== 'medium' && body?.difficulty !== 'hard') {
            return Response.json({ ok: false, error: 'invalid_difficulty' }, { status: 400 })
          }
          difficulty = body.difficulty
        }

        const maxPlayers = Math.min(8, Math.max(2, Number(body?.maxPlayers) || 8))

        const db = getDb()
        let roomId = generateRoomCode()
        for (let attempt = 0; attempt < 5; attempt++) {
          const existing = await db.prepare('SELECT id FROM rooms WHERE id = ?').bind(roomId).first()
          if (!existing) break
          roomId = generateRoomCode()
        }

        await db
          .prepare(
            'INSERT INTO rooms (id, mode, difficulty, max_players, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
          )
          .bind(roomId, mode, difficulty, maxPlayers, 'waiting', Date.now())
          .run()

        return Response.json({ ok: true, roomId })
      },
    },
  },
})
```

- [ ] **Step 4: Join route**

```ts
// 양세찬게임/app/src/routes/api/rooms/$roomId/join.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'

export const Route = createFileRoute('/api/rooms/$roomId/join')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const roomId = params.roomId
        const body = await request.json().catch(() => null) as { nickname?: string } | null
        const nickname = body?.nickname?.trim().slice(0, 12)
        if (!nickname) {
          return Response.json({ ok: false, error: 'invalid_nickname' }, { status: 400 })
        }

        const db = getDb()
        const room = await db.prepare('SELECT * FROM rooms WHERE id = ?').bind(roomId).first<{
          id: string
          status: string
          max_players: number
        }>()
        if (!room) {
          return Response.json({ ok: false, error: 'room_not_found' }, { status: 404 })
        }
        if (room.status !== 'waiting') {
          return Response.json({ ok: false, error: 'room_already_started' }, { status: 409 })
        }

        const { count } = (await db
          .prepare('SELECT COUNT(*) as count FROM players WHERE room_id = ?')
          .bind(roomId)
          .first<{ count: number }>()) ?? { count: 0 }
        if (count >= room.max_players) {
          return Response.json({ ok: false, error: 'room_full' }, { status: 409 })
        }

        const dup = await db
          .prepare('SELECT id FROM players WHERE room_id = ? AND LOWER(nickname) = LOWER(?)')
          .bind(roomId, nickname)
          .first()
        if (dup) {
          return Response.json({ ok: false, error: 'nickname_taken' }, { status: 409 })
        }

        const playerId = crypto.randomUUID()
        await db
          .prepare('INSERT INTO players (id, room_id, nickname, joined_at) VALUES (?, ?, ?, ?)')
          .bind(playerId, roomId, nickname, Date.now())
          .run()

        return Response.json({ ok: true, playerId })
      },
    },
  },
})
```

- [ ] **Step 5: Commit, push, deploy**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/lib/room-code.server.ts src/lib/name-bank.ts src/routes/api/rooms/index.ts src/routes/api/rooms/\$roomId/join.ts
git commit -m "Add room creation, join API, and preset name bank"
git push
```

Call `deploy_website` with `env='preview'`. Note the preview URL (`<preview>`).

- [ ] **Step 6: Verify with curl**

```bash
curl -s -X POST "<preview>/api/rooms" -H 'content-type: application/json' \
  -d '{"mode":"preset","difficulty":"easy","maxPlayers":4}'
```
Expected: `{"ok":true,"roomId":"XXXXXX"}`. Take that `roomId` and:

```bash
curl -s -X POST "<preview>/api/rooms/<roomId>/join" -H 'content-type: application/json' \
  -d '{"nickname":"세찬"}'
```
Expected: `{"ok":true,"playerId":"<uuid>"}`.

Then confirm with `website_db` (`operation='rows'`, `table='players'`) that a row with `nickname='세찬'` exists.

---

### Task 3: 상태 조회 + 후보 제출 API

**Files:**
- Create: `양세찬게임/app/src/routes/api/rooms/$roomId/index.ts`
- Create: `양세찬게임/app/src/routes/api/rooms/$roomId/submit.ts`

**Interfaces:**
- Consumes: `getDb()` (Task 1).
- Produces: `GET /api/rooms/:roomId?playerId=<id>` response shape:
  ```ts
  {
    ok: true,
    room: { id: string, mode: 'preset'|'custom', difficulty: string|null, maxPlayers: number, status: 'waiting'|'playing'|'finished' },
    players: Array<{ id: string, nickname: string, hasSubmitted: boolean, isFinished: boolean, isSelf: boolean, assignedName: string | null }>,
  }
  ```
  used by the frontend in Tasks 6–9.
- Produces: `POST /api/rooms/:roomId/submit` → `{ ok: true }` — used by Task 7.

- [ ] **Step 1: Room state route**

```ts
// 양세찬게임/app/src/routes/api/rooms/$roomId/index.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'

export const Route = createFileRoute('/api/rooms/$roomId/')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const roomId = params.roomId
        const url = new URL(request.url)
        const requesterId = url.searchParams.get('playerId') ?? ''

        const db = getDb()
        const room = await db.prepare('SELECT * FROM rooms WHERE id = ?').bind(roomId).first<{
          id: string
          mode: string
          difficulty: string | null
          max_players: number
          status: string
        }>()
        if (!room) {
          return Response.json({ ok: false, error: 'room_not_found' }, { status: 404 })
        }

        const { results } = await db
          .prepare('SELECT * FROM players WHERE room_id = ? ORDER BY joined_at ASC')
          .bind(roomId)
          .all<{
            id: string
            nickname: string
            submitted_text: string | null
            assigned_name: string | null
            is_finished: number
          }>()

        const players = results.map((p) => {
          const isSelf = p.id === requesterId
          const canSeeAssignedName = !isSelf || p.is_finished === 1
          return {
            id: p.id,
            nickname: p.nickname,
            hasSubmitted: p.submitted_text !== null,
            isFinished: p.is_finished === 1,
            isSelf,
            assignedName: canSeeAssignedName ? p.assigned_name : null,
          }
        })

        return Response.json({
          ok: true,
          room: {
            id: room.id,
            mode: room.mode,
            difficulty: room.difficulty,
            maxPlayers: room.max_players,
            status: room.status,
          },
          players,
        })
      },
    },
  },
})
```

- [ ] **Step 2: Submit-candidate route**

```ts
// 양세찬게임/app/src/routes/api/rooms/$roomId/submit.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'

export const Route = createFileRoute('/api/rooms/$roomId/submit')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const roomId = params.roomId
        const body = await request.json().catch(() => null) as { playerId?: string; text?: string } | null
        const playerId = body?.playerId
        const text = body?.text?.trim().slice(0, 20)
        if (!playerId || !text) {
          return Response.json({ ok: false, error: 'invalid_input' }, { status: 400 })
        }

        const db = getDb()
        const room = await db.prepare('SELECT mode, status FROM rooms WHERE id = ?').bind(roomId).first<{
          mode: string
          status: string
        }>()
        if (!room) {
          return Response.json({ ok: false, error: 'room_not_found' }, { status: 404 })
        }
        if (room.mode !== 'custom') {
          return Response.json({ ok: false, error: 'not_custom_mode' }, { status: 409 })
        }
        if (room.status !== 'waiting') {
          return Response.json({ ok: false, error: 'room_already_started' }, { status: 409 })
        }

        const result = await db
          .prepare('UPDATE players SET submitted_text = ? WHERE id = ? AND room_id = ?')
          .bind(text, playerId, roomId)
          .run()
        if (result.meta.changes === 0) {
          return Response.json({ ok: false, error: 'player_not_found' }, { status: 404 })
        }

        return Response.json({ ok: true })
      },
    },
  },
})
```

- [ ] **Step 3: Commit, push, deploy**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/routes/api/rooms/\$roomId/index.ts src/routes/api/rooms/\$roomId/submit.ts
git commit -m "Add room state polling and candidate submission API"
git push
```

Call `deploy_website` with `env='preview'`.

- [ ] **Step 4: Verify with curl**

Reuse the `roomId`/`playerId` from Task 2 (or create a fresh preset room + join for a clean test):

```bash
curl -s "<preview>/api/rooms/<roomId>?playerId=<playerId>"
```
Expected: `{"ok":true,"room":{...,"status":"waiting"},"players":[{"nickname":"세찬","isSelf":true,"assignedName":null,...}]}`.

For submit, create a **custom-mode** room and join two players, then:

```bash
curl -s -X POST "<preview>/api/rooms/<customRoomId>/submit" -H 'content-type: application/json' \
  -d '{"playerId":"<playerA>","text":"손흥민"}'
```
Expected: `{"ok":true}`. Re-run the `GET` for that room and confirm `hasSubmitted: true` for player A.

---

### Task 4: 시작(배정) + 다시하기 API

**Files:**
- Create: `양세찬게임/app/src/lib/derangement.ts`
- Create: `양세찬게임/app/src/lib/assign-names.server.ts`
- Create: `양세찬게임/app/src/routes/api/rooms/$roomId/start.ts`
- Create: `양세찬게임/app/src/routes/api/rooms/$roomId/restart.ts`

**Interfaces:**
- Consumes: `getDb()` (Task 1), `drawUniqueNames()` (Task 2).
- Produces: `randomDerangement(n: number): number[]` (a permutation of indices where `perm[i] !== i` for all `i`).
- Produces: `assignNames(db, roomId, mode, difficulty, players): Promise<void>` from `assign-names.server.ts` — shared by both `start.ts` and `restart.ts` so the assignment logic lives in exactly one place.
- Produces: `POST /api/rooms/:roomId/start` → `{ ok: true }`; `POST /api/rooms/:roomId/restart` → `{ ok: true }` — used by Tasks 7 and 9.

- [ ] **Step 1: Derangement helper**

```ts
// 양세찬게임/app/src/lib/derangement.ts
export function randomDerangement(n: number): number[] {
  if (n < 2) throw new Error('Derangement requires at least 2 items')
  const indices = Array.from({ length: n }, (_, i) => i)
  let attempt: number[]
  do {
    attempt = shuffle([...indices])
  } while (attempt.some((v, i) => v === i))
  return attempt
}

function shuffle(arr: number[]): number[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(secureRandom() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

function secureRandom(): number {
  const buf = new Uint32Array(1)
  crypto.getRandomValues(buf)
  return buf[0] / 0xffffffff
}
```

- [ ] **Step 2: Shared assignment logic (library module, not a route)**

```ts
// 양세찬게임/app/src/lib/assign-names.server.ts
import { drawUniqueNames, type Difficulty } from '~/lib/name-bank'
import { randomDerangement } from '~/lib/derangement'

export type PlayerRow = { id: string; submitted_text: string | null }

export async function assignNames(
  db: D1Database,
  mode: string,
  difficulty: Difficulty | null,
  players: PlayerRow[],
) {
  let assigned: string[]

  if (mode === 'preset') {
    assigned = drawUniqueNames(difficulty as Difficulty, players.length)
  } else if (players.length === 2) {
    assigned = [players[1].submitted_text as string, players[0].submitted_text as string]
  } else {
    const texts = players.map((p) => p.submitted_text as string)
    const perm = randomDerangement(players.length)
    assigned = perm.map((sourceIndex) => texts[sourceIndex])
  }

  const statements = players.map((p, i) =>
    db.prepare('UPDATE players SET assigned_name = ?, is_finished = 0 WHERE id = ?').bind(assigned[i], p.id),
  )
  await db.batch(statements)
}
```

- [ ] **Step 3: Start route**

```ts
// 양세찬게임/app/src/routes/api/rooms/$roomId/start.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'
import type { Difficulty } from '~/lib/name-bank'
import { assignNames, type PlayerRow } from '~/lib/assign-names.server'

export const Route = createFileRoute('/api/rooms/$roomId/start')({
  server: {
    handlers: {
      POST: async ({ params }) => {
        const roomId = params.roomId
        const db = getDb()

        const room = await db.prepare('SELECT * FROM rooms WHERE id = ?').bind(roomId).first<{
          id: string
          mode: string
          difficulty: Difficulty | null
          status: string
        }>()
        if (!room) {
          return Response.json({ ok: false, error: 'room_not_found' }, { status: 404 })
        }
        if (room.status !== 'waiting') {
          return Response.json({ ok: false, error: 'room_already_started' }, { status: 409 })
        }

        const { results: players } = await db
          .prepare('SELECT id, submitted_text FROM players WHERE room_id = ? ORDER BY joined_at ASC')
          .bind(roomId)
          .all<PlayerRow>()

        if (players.length < 2) {
          return Response.json({ ok: false, error: 'need_more_players' }, { status: 400 })
        }
        if (room.mode === 'custom' && players.some((p) => !p.submitted_text)) {
          return Response.json({ ok: false, error: 'missing_submissions' }, { status: 400 })
        }

        await assignNames(db, room.mode, room.difficulty, players)
        await db.prepare("UPDATE rooms SET status = 'playing' WHERE id = ?").bind(roomId).run()

        return Response.json({ ok: true })
      },
    },
  },
})
```

- [ ] **Step 4: Restart route (reuses `assignNames`)**

```ts
// 양세찬게임/app/src/routes/api/rooms/$roomId/restart.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'
import type { Difficulty } from '~/lib/name-bank'
import { assignNames, type PlayerRow } from '~/lib/assign-names.server'

export const Route = createFileRoute('/api/rooms/$roomId/restart')({
  server: {
    handlers: {
      POST: async ({ params }) => {
        const roomId = params.roomId
        const db = getDb()

        const room = await db.prepare('SELECT * FROM rooms WHERE id = ?').bind(roomId).first<{
          id: string
          mode: string
          difficulty: Difficulty | null
          status: string
        }>()
        if (!room) {
          return Response.json({ ok: false, error: 'room_not_found' }, { status: 404 })
        }
        if (room.status === 'waiting') {
          return Response.json({ ok: false, error: 'not_started_yet' }, { status: 409 })
        }

        const { results: players } = await db
          .prepare('SELECT id, submitted_text FROM players WHERE room_id = ? ORDER BY joined_at ASC')
          .bind(roomId)
          .all<PlayerRow>()

        await assignNames(db, room.mode, room.difficulty, players)
        await db.prepare("UPDATE rooms SET status = 'playing' WHERE id = ?").bind(roomId).run()

        return Response.json({ ok: true })
      },
    },
  },
})
```

- [ ] **Step 5: Commit, push, deploy**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/lib/derangement.ts src/lib/assign-names.server.ts src/routes/api/rooms/\$roomId/start.ts src/routes/api/rooms/\$roomId/restart.ts
git commit -m "Add name assignment (start/restart) API"
git push
```

Call `deploy_website` with `env='preview'`.

- [ ] **Step 6: Verify with curl + website_db**

Preset room, 3 players joined (`p1`, `p2`, `p3`):

```bash
curl -s -X POST "<preview>/api/rooms/<roomId>/start"
```
Expected: `{"ok":true}`. Then:

```bash
curl -s "<preview>/api/rooms/<roomId>?playerId=<p1>"
```
Expected `room.status: "playing"`, and `players` shows `assignedName` for `p2`/`p3` but `null` for `p1` (`isSelf: true`, `isFinished: false`).

Use `website_db` (`operation='query'`, `sql='SELECT id, submitted_text, assigned_name FROM players WHERE room_id = "<customRoomId>"'`) on a **custom 3-player** room to confirm no row has `assigned_name = submitted_text` for itself (no self-assignment).

---

### Task 5: 맞았어요(reveal) API

**Files:**
- Create: `양세찬게임/app/src/routes/api/rooms/$roomId/reveal.ts`

**Interfaces:**
- Consumes: `getDb()` (Task 1).
- Produces: `POST /api/rooms/:roomId/reveal` → `{ ok: true }`, flips `room.status` to `'finished'` once every player is finished — used by Task 8.

- [ ] **Step 1: Reveal route**

```ts
// 양세찬게임/app/src/routes/api/rooms/$roomId/reveal.ts
import { createFileRoute } from '@tanstack/react-router'
import { getDb } from '~/lib/bindings.server'

export const Route = createFileRoute('/api/rooms/$roomId/reveal')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const roomId = params.roomId
        const body = await request.json().catch(() => null) as { targetPlayerId?: string } | null
        const targetPlayerId = body?.targetPlayerId
        if (!targetPlayerId) {
          return Response.json({ ok: false, error: 'invalid_input' }, { status: 400 })
        }

        const db = getDb()
        const room = await db.prepare('SELECT status FROM rooms WHERE id = ?').bind(roomId).first<{
          status: string
        }>()
        if (!room) {
          return Response.json({ ok: false, error: 'room_not_found' }, { status: 404 })
        }
        if (room.status !== 'playing') {
          return Response.json({ ok: false, error: 'room_not_playing' }, { status: 409 })
        }

        const result = await db
          .prepare('UPDATE players SET is_finished = 1 WHERE id = ? AND room_id = ?')
          .bind(targetPlayerId, roomId)
          .run()
        if (result.meta.changes === 0) {
          return Response.json({ ok: false, error: 'player_not_found' }, { status: 404 })
        }

        const { count: remaining } = (await db
          .prepare('SELECT COUNT(*) as count FROM players WHERE room_id = ? AND is_finished = 0')
          .bind(roomId)
          .first<{ count: number }>()) ?? { count: 0 }

        if (remaining === 0) {
          await db.prepare("UPDATE rooms SET status = 'finished' WHERE id = ?").bind(roomId).run()
        }

        return Response.json({ ok: true })
      },
    },
  },
})
```

- [ ] **Step 2: Commit, push, deploy**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/routes/api/rooms/\$roomId/reveal.ts
git commit -m "Add reveal API and finished-room transition"
git push
```

Call `deploy_website` with `env='preview'`.

- [ ] **Step 3: Verify with curl**

Using the 3-player preset room from Task 4 (now `playing`), reveal all three players one at a time:

```bash
curl -s -X POST "<preview>/api/rooms/<roomId>/reveal" -H 'content-type: application/json' -d '{"targetPlayerId":"<p1>"}'
curl -s "<preview>/api/rooms/<roomId>?playerId=<p1>"
```
After the first reveal, expect `p1`'s own row to now show `isFinished: true` and a non-null `assignedName` (self-reveal works). Repeat for `p2`, `p3`; after the third reveal:

```bash
curl -s "<preview>/api/rooms/<roomId>?playerId=<p1>"
```
Expected `room.status: "finished"`.

---

### Task 6: 홈 화면 + 방 만들기 화면

**Files:**
- Create: `양세찬게임/app/src/routes/index.tsx`
- Create: `양세찬게임/app/src/routes/create.tsx`

**Interfaces:**
- Consumes: `POST /api/rooms` (Task 2).
- Produces: navigation to `/room/$roomId` — consumed by Task 7.

- [ ] **Step 1: Home screen**

```tsx
// 양세찬게임/app/src/routes/index.tsx
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/')({
  component: HomePage,
})

function HomePage() {
  const navigate = useNavigate()
  const [joinCode, setJoinCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleJoinByCode(e: React.FormEvent) {
    e.preventDefault()
    const code = joinCode.trim().toUpperCase()
    if (!code) return
    const res = await fetch(`/api/rooms/${code}`)
    if (!res.ok) {
      setError('그런 방이 없어요. 코드를 다시 확인해주세요.')
      return
    }
    navigate({ to: '/room/$roomId', params: { roomId: code } })
  }

  return (
    <main className="min-h-dvh bg-gradient-to-b from-amber-100 via-orange-50 to-white flex flex-col items-center justify-center gap-8 px-6 py-12">
      <div className="text-center space-y-3">
        <p className="text-sm font-bold tracking-widest text-orange-500 uppercase">양세찬 게임</p>
        <h1 className="text-4xl font-black text-neutral-900 leading-tight">
          내 이름만<br />나만 몰라!
        </h1>
        <p className="text-neutral-500 text-sm">친구들과 각자 폰으로 같이 즐기는 이름 맞추기 게임</p>
      </div>

      <div className="w-full max-w-sm space-y-4">
        <Link
          to="/create"
          className="block w-full text-center rounded-2xl bg-orange-500 text-white font-bold text-lg py-4 shadow-lg shadow-orange-200 active:scale-95 transition-transform"
        >
          방 만들기
        </Link>

        <form onSubmit={handleJoinByCode} className="flex flex-col gap-2">
          <input
            value={joinCode}
            onChange={(e) => {
              setJoinCode(e.target.value)
              setError(null)
            }}
            placeholder="방 코드 입력 (예: AB12CD)"
            maxLength={6}
            className="w-full rounded-2xl border-2 border-orange-200 bg-white px-4 py-4 text-center text-lg font-bold tracking-widest uppercase focus:border-orange-500 focus:outline-none"
          />
          <button
            type="submit"
            className="w-full rounded-2xl bg-white border-2 border-orange-300 text-orange-600 font-bold text-lg py-4 active:scale-95 transition-transform"
          >
            코드로 참가하기
          </button>
          {error && <p className="text-red-500 text-sm text-center">{error}</p>}
        </form>
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Room settings screen**

```tsx
// 양세찬게임/app/src/routes/create.tsx
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/create')({
  component: CreateRoomPage,
})

const DIFFICULTIES = [
  { value: 'easy', label: '쉬움', desc: '남녀노소 누구나 아는 이름' },
  { value: 'medium', label: '보통', desc: '꽤 유명하지만 조금 더 관심 필요' },
  { value: 'hard', label: '어려움', desc: '팬덤/특정 세대가 아는 이름' },
] as const

function CreateRoomPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'preset' | 'custom'>('preset')
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('easy')
  const [maxPlayers, setMaxPlayers] = useState(8)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleCreate() {
    setLoading(true)
    setError(null)
    const res = await fetch('/api/rooms', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ mode, difficulty: mode === 'preset' ? difficulty : undefined, maxPlayers }),
    })
    const data = await res.json() as { ok: boolean; roomId?: string }
    setLoading(false)
    if (!data.ok || !data.roomId) {
      setError('방 생성에 실패했어요. 다시 시도해주세요.')
      return
    }
    navigate({ to: '/room/$roomId', params: { roomId: data.roomId } })
  }

  return (
    <main className="min-h-dvh bg-gradient-to-b from-amber-100 via-orange-50 to-white px-6 py-10 flex flex-col gap-8">
      <h1 className="text-2xl font-black text-neutral-900">방 설정</h1>

      <section className="space-y-3">
        <p className="font-bold text-neutral-700">이름은 어떻게 정할까요?</p>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => setMode('preset')}
            className={`rounded-2xl border-2 py-4 px-3 text-left transition-colors ${mode === 'preset' ? 'border-orange-500 bg-orange-50' : 'border-neutral-200 bg-white'}`}
          >
            <p className="font-bold">프리셋</p>
            <p className="text-xs text-neutral-500 mt-1">자동으로 유명인 배정</p>
          </button>
          <button
            onClick={() => setMode('custom')}
            className={`rounded-2xl border-2 py-4 px-3 text-left transition-colors ${mode === 'custom' ? 'border-orange-500 bg-orange-50' : 'border-neutral-200 bg-white'}`}
          >
            <p className="font-bold">직접입력</p>
            <p className="text-xs text-neutral-500 mt-1">친구들이 직접 이름 제출</p>
          </button>
        </div>
      </section>

      {mode === 'preset' && (
        <section className="space-y-3">
          <p className="font-bold text-neutral-700">난이도</p>
          <div className="flex flex-col gap-2">
            {DIFFICULTIES.map((d) => (
              <button
                key={d.value}
                onClick={() => setDifficulty(d.value)}
                className={`rounded-2xl border-2 py-3 px-4 text-left transition-colors ${difficulty === d.value ? 'border-orange-500 bg-orange-50' : 'border-neutral-200 bg-white'}`}
              >
                <p className="font-bold">{d.label}</p>
                <p className="text-xs text-neutral-500">{d.desc}</p>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <p className="font-bold text-neutral-700">최대 인원: {maxPlayers}명</p>
        <input
          type="range"
          min={2}
          max={8}
          value={maxPlayers}
          onChange={(e) => setMaxPlayers(Number(e.target.value))}
          className="w-full accent-orange-500"
        />
      </section>

      <button
        onClick={handleCreate}
        disabled={loading}
        className="mt-auto w-full rounded-2xl bg-orange-500 text-white font-bold text-lg py-4 shadow-lg shadow-orange-200 active:scale-95 transition-transform disabled:opacity-50"
      >
        {loading ? '만드는 중...' : '방 만들기'}
      </button>
      {error && <p className="text-red-500 text-sm text-center">{error}</p>}
    </main>
  )
}
```

- [ ] **Step 3: Commit, push, deploy, manual check**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/routes/index.tsx src/routes/create.tsx
git commit -m "Add home and create-room screens"
git push
```

Call `deploy_website` with `env='preview'`. Open the preview URL, click "방 만들기", pick preset/easy, tap "방 만들기", and confirm the browser navigates to `/room/<code>` (a 404 page is expected here — Task 7 builds that route).

---

### Task 7: 참가/대기실 화면

**Files:**
- Create: `양세찬게임/app/src/routes/room/$roomId/index.tsx`

**Interfaces:**
- Consumes: `GET /api/rooms/:roomId` (Task 3), `POST /api/rooms/:roomId/join` (Task 2), `POST /api/rooms/:roomId/submit` (Task 3), `POST /api/rooms/:roomId/start` (Task 4).
- Produces: this file also hosts the `playing`/`finished` views built in Tasks 8–9 (same component, branching on `room.status`) — note the branch points clearly for those tasks to extend.

- [ ] **Step 1: Room page with polling + waiting-room view**

```tsx
// 양세찬게임/app/src/routes/room/$roomId/index.tsx
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

type Player = {
  id: string
  nickname: string
  hasSubmitted: boolean
  isFinished: boolean
  isSelf: boolean
  assignedName: string | null
}
type RoomState = {
  room: { id: string; mode: 'preset' | 'custom'; difficulty: string | null; maxPlayers: number; status: 'waiting' | 'playing' | 'finished' }
  players: Player[]
}

export const Route = createFileRoute('/room/$roomId/')({
  component: RoomPage,
})

function storageKey(roomId: string) {
  return `yangsechan:${roomId}:playerId`
}

function RoomPage() {
  const { roomId } = Route.useParams()
  const [playerId, setPlayerId] = useState<string | null>(null)
  const [state, setState] = useState<RoomState | null>(null)
  const [nickname, setNickname] = useState('')
  const [candidateText, setCandidateText] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    setPlayerId(window.localStorage.getItem(storageKey(roomId)))
  }, [roomId])

  useEffect(() => {
    let cancelled = false
    async function poll() {
      const url = playerId ? `/api/rooms/${roomId}?playerId=${playerId}` : `/api/rooms/${roomId}`
      const res = await fetch(url)
      if (!res.ok) return
      const data = (await res.json()) as { ok: boolean } & RoomState
      if (!cancelled && data.ok) setState(data)
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [roomId, playerId])

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault()
    const name = nickname.trim()
    if (!name) return
    const res = await fetch(`/api/rooms/${roomId}/join`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ nickname: name }),
    })
    const data = (await res.json()) as { ok: boolean; playerId?: string; error?: string }
    if (!data.ok || !data.playerId) {
      setError(data.error === 'nickname_taken' ? '이미 사용 중인 이름이에요.' : '참가에 실패했어요.')
      return
    }
    window.localStorage.setItem(storageKey(roomId), data.playerId)
    setPlayerId(data.playerId)
  }

  async function handleSubmitCandidate(e: React.FormEvent) {
    e.preventDefault()
    if (!playerId || !candidateText.trim()) return
    await fetch(`/api/rooms/${roomId}/submit`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ playerId, text: candidateText.trim() }),
    })
    setCandidateText('')
  }

  async function handleStart() {
    const res = await fetch(`/api/rooms/${roomId}/start`, { method: 'POST' })
    const data = (await res.json()) as { ok: boolean; error?: string }
    if (!data.ok) {
      setError(
        data.error === 'missing_submissions'
          ? '아직 이름을 안 낸 사람이 있어요.'
          : data.error === 'need_more_players'
            ? '최소 2명이 필요해요.'
            : '시작에 실패했어요.',
      )
    }
  }

  if (!state) {
    return <main className="min-h-dvh flex items-center justify-center text-neutral-400">불러오는 중...</main>
  }

  const { room, players } = state

  // Not joined yet
  if (!playerId) {
    return (
      <main className="min-h-dvh bg-gradient-to-b from-amber-100 via-orange-50 to-white px-6 py-12 flex flex-col items-center justify-center gap-6">
        <p className="text-sm font-bold tracking-widest text-orange-500">방 코드 {roomId}</p>
        <h1 className="text-2xl font-black">닉네임을 입력해주세요</h1>
        <form onSubmit={handleJoin} className="w-full max-w-sm flex flex-col gap-3">
          <input
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder="내 닉네임"
            maxLength={12}
            className="w-full rounded-2xl border-2 border-orange-200 bg-white px-4 py-4 text-center text-lg font-bold focus:border-orange-500 focus:outline-none"
          />
          <button type="submit" className="w-full rounded-2xl bg-orange-500 text-white font-bold text-lg py-4 active:scale-95 transition-transform">
            참가하기
          </button>
          {error && <p className="text-red-500 text-sm text-center">{error}</p>}
        </form>
      </main>
    )
  }

  // Playing / finished views are added in Tasks 8 and 9, branching here:
  if (room.status === 'playing') {
    return <PlayingView roomId={roomId} playerId={playerId} players={players} onError={setError} error={error} />
  }
  if (room.status === 'finished') {
    return <FinishedView roomId={roomId} players={players} onError={setError} error={error} />
  }

  // Waiting room (status === 'waiting')
  const needsSubmission = room.mode === 'custom'
  const self = players.find((p) => p.isSelf)
  const submittedCount = players.filter((p) => p.hasSubmitted).length
  const canStart = players.length >= 2 && (!needsSubmission || submittedCount >= players.length)

  return (
    <main className="min-h-dvh bg-gradient-to-b from-amber-100 via-orange-50 to-white px-6 py-10 flex flex-col gap-6">
      <div className="text-center">
        <p className="text-sm font-bold tracking-widest text-orange-500">방 코드</p>
        <p className="text-3xl font-black tracking-widest">{roomId}</p>
      </div>

      <section className="rounded-2xl bg-white border-2 border-orange-100 p-4">
        <p className="font-bold text-neutral-700 mb-2">참가자 ({players.length}/{room.maxPlayers})</p>
        <ul className="space-y-1">
          {players.map((p) => (
            <li key={p.id} className="flex items-center justify-between text-sm">
              <span>{p.nickname}{p.isSelf ? ' (나)' : ''}</span>
              {needsSubmission && <span className={p.hasSubmitted ? 'text-green-600' : 'text-neutral-400'}>{p.hasSubmitted ? '제출완료' : '대기중'}</span>}
            </li>
          ))}
        </ul>
      </section>

      {needsSubmission && self && !self.hasSubmitted && (
        <form onSubmit={handleSubmitCandidate} className="space-y-2">
          <p className="font-bold text-neutral-700">
            {players.length === 2 ? '상대방에게 줄 이름을 입력하세요' : '누군가에게 배정될 이름 후보를 입력하세요'}
          </p>
          <input
            value={candidateText}
            onChange={(e) => setCandidateText(e.target.value)}
            placeholder="예: 손흥민"
            maxLength={20}
            className="w-full rounded-2xl border-2 border-orange-200 bg-white px-4 py-3 text-center font-bold focus:border-orange-500 focus:outline-none"
          />
          <button type="submit" className="w-full rounded-2xl bg-white border-2 border-orange-300 text-orange-600 font-bold py-3 active:scale-95 transition-transform">
            제출하기
          </button>
        </form>
      )}

      <button
        onClick={handleStart}
        disabled={!canStart}
        className="mt-auto w-full rounded-2xl bg-orange-500 text-white font-bold text-lg py-4 shadow-lg shadow-orange-200 active:scale-95 transition-transform disabled:opacity-40"
      >
        시작하기
      </button>
      {error && <p className="text-red-500 text-sm text-center">{error}</p>}
    </main>
  )
}

function PlayingView(_props: {
  roomId: string
  playerId: string
  players: Player[]
  error: string | null
  onError: (e: string | null) => void
}) {
  return <main className="min-h-dvh flex items-center justify-center text-neutral-400">게임 화면은 Task 8에서 구현</main>
}

function FinishedView(_props: {
  roomId: string
  players: Player[]
  error: string | null
  onError: (e: string | null) => void
}) {
  return <main className="min-h-dvh flex items-center justify-center text-neutral-400">완료 화면은 Task 9에서 구현</main>
}
```

- [ ] **Step 2: Commit, push, deploy, manual check**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/routes/room/\$roomId/index.tsx
git commit -m "Add join/waiting-room screen with 2s polling"
git push
```

Call `deploy_website` with `env='preview'`. Open two browser tabs (or your phone + laptop) to the same preview `/room/<code>` (create a preset room from Task 6's flow first), join with two different nicknames, and confirm both tabs show both nicknames within ~2 seconds without a manual refresh, and the "시작하기" button enables once ≥2 players joined.

---

### Task 8: 게임 화면 (roster + 맞았어요 버튼)

**Files:**
- Modify: `양세찬게임/app/src/routes/room/$roomId/index.tsx` (replace the `PlayingView` stub from Task 7)

**Interfaces:**
- Consumes: `POST /api/rooms/:roomId/reveal` (Task 5); reuses the `players`/`Player` shape already polled by the parent `RoomPage`.

- [ ] **Step 1: Implement `PlayingView`**

Replace the `PlayingView` function body from Task 7 with:

```tsx
function PlayingView({
  roomId,
  playerId,
  players,
  error,
  onError,
}: {
  roomId: string
  playerId: string
  players: Player[]
  error: string | null
  onError: (e: string | null) => void
}) {
  async function handleReveal(targetPlayerId: string) {
    const res = await fetch(`/api/rooms/${roomId}/reveal`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ targetPlayerId }),
    })
    const data = (await res.json()) as { ok: boolean }
    if (!data.ok) onError('처리에 실패했어요. 다시 시도해주세요.')
  }

  const self = players.find((p) => p.id === playerId)
  const others = players.filter((p) => p.id !== playerId)

  return (
    <main className="min-h-dvh bg-gradient-to-b from-amber-100 via-orange-50 to-white px-6 py-10 flex flex-col gap-6">
      <div className="text-center space-y-1">
        <p className="text-sm font-bold tracking-widest text-orange-500">내 정답은 나만 안 보여요!</p>
        {self?.isFinished ? (
          <p className="text-2xl font-black text-green-600">내 정답: {self.assignedName}</p>
        ) : (
          <p className="text-lg font-bold text-neutral-400">?????</p>
        )}
      </div>

      <ul className="space-y-3">
        {others.map((p) => (
          <li key={p.id} className="flex items-center justify-between rounded-2xl bg-white border-2 border-orange-100 p-4">
            <div>
              <p className="font-bold">{p.nickname}</p>
              <p className="text-lg font-black text-orange-600">{p.assignedName}</p>
            </div>
            {!p.isFinished && (
              <button
                onClick={() => handleReveal(p.id)}
                className="rounded-xl bg-orange-500 text-white font-bold px-4 py-2 text-sm active:scale-95 transition-transform"
              >
                맞았어요!
              </button>
            )}
            {p.isFinished && <span className="text-green-600 font-bold text-sm">완료</span>}
          </li>
        ))}
      </ul>

      {error && <p className="text-red-500 text-sm text-center">{error}</p>}
    </main>
  )
}
```

- [ ] **Step 2: Commit, push, deploy, manual check**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/routes/room/\$roomId/index.tsx
git commit -m "Implement game screen with reveal button"
git push
```

Call `deploy_website` with `env='preview'`. Using the same two-tab setup as Task 7, tap "시작하기" in one tab, confirm both tabs switch to the game screen within 2 seconds, each tab shows the OTHER player's name but not its own, tap "맞았어요!" for the other player in one tab, and confirm that player's own tab reveals their name within 2 seconds.

---

### Task 9: 완료 화면

**Files:**
- Modify: `양세찬게임/app/src/routes/room/$roomId/index.tsx` (replace the `FinishedView` stub)

**Interfaces:**
- Consumes: `POST /api/rooms/:roomId/restart` (Task 4).

- [ ] **Step 1: Implement `FinishedView`**

```tsx
function FinishedView({
  roomId,
  players,
  error,
  onError,
}: {
  roomId: string
  players: Player[]
  error: string | null
  onError: (e: string | null) => void
}) {
  async function handleRestart() {
    const res = await fetch(`/api/rooms/${roomId}/restart`, { method: 'POST' })
    const data = (await res.json()) as { ok: boolean }
    if (!data.ok) onError('다시 시작하지 못했어요.')
  }

  return (
    <main className="min-h-dvh bg-gradient-to-b from-amber-100 via-orange-50 to-white px-6 py-10 flex flex-col gap-6">
      <h1 className="text-2xl font-black text-center">🎉 모두 맞혔어요!</h1>
      <ul className="space-y-2">
        {players.map((p) => (
          <li key={p.id} className="flex items-center justify-between rounded-2xl bg-white border-2 border-orange-100 p-4">
            <span className="font-bold">{p.nickname}</span>
            <span className="text-orange-600 font-black">{p.assignedName}</span>
          </li>
        ))}
      </ul>
      <button
        onClick={handleRestart}
        className="mt-auto w-full rounded-2xl bg-orange-500 text-white font-bold text-lg py-4 shadow-lg shadow-orange-200 active:scale-95 transition-transform"
      >
        다시하기
      </button>
      {error && <p className="text-red-500 text-sm text-center">{error}</p>}
    </main>
  )
}
```

- [ ] **Step 2: Commit, push, deploy, manual check**

```bash
cd "/Users/donghwikim/바이브코딩/양세찬게임/app"
git add src/routes/room/\$roomId/index.tsx
git commit -m "Implement finished screen with restart"
git push
```

Call `deploy_website` with `env='preview'`. Continue the two-tab test from Task 8: reveal both players, confirm both tabs auto-switch to the finished screen showing everyone's names within 2 seconds, tap "다시하기", and confirm both tabs return to the game screen with newly (re-)assigned names.

---

### Task 10: 전체 흐름 점검 및 정리

**Files:** none (verification-only task)

- [ ] **Step 1: End-to-end preset-mode check (3+ players)**

On the current preview URL: create a preset/easy room with max players 4, join from 3 separate browser tabs with distinct nicknames, start, reveal all three, confirm the finished screen, restart, and confirm new names differ from the first round for at least one player.

- [ ] **Step 2: End-to-end custom-mode check (2 players)**

Create a custom-mode room, join with exactly 2 nicknames, confirm each tab's submission prompt says "상대방에게 줄 이름을 입력하세요", submit different names from each tab, confirm "시작하기" enables only after both submit, start, and confirm each player sees exactly the name the OTHER player typed (not shuffled).

- [ ] **Step 3: End-to-end custom-mode check (3+ players)**

Create a custom-mode room with 3 tabs, submit a distinct name from each, start, and use `website_db` (`operation='query'`) to confirm no player's `assigned_name` equals their own `submitted_text`.

- [ ] **Step 4: Report the preview link**

Tell the user the preview URL and that production deploy (a permanent public link) is available on request via `deploy_website` with `env='production'`.
