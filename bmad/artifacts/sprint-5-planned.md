# Sprint 5 — IMAP IDLE vrai push + Webhook Proton

**Goal:** Remplacer le polling 30s par de vrais événements push Proton.

## Stories

| ID | Titre | Effort |
|----|-------|--------|
| S5-01 | Proton EventLoop — poll /core/v4/events | M |
| S5-02 | Mapping event Proton → IMAP untagged push | M |
| S5-03 | IDLE upgrade : event-driven au lieu de polling | S |

## Design

Proton expose `/core/v4/events/{EventID}` — long-poll qui retourne dès qu'un event se produit.

```
EventLoop (asyncio task)
    → GET /core/v4/events/{last_id}   (long-poll, timeout 25s)
    → Nouvel event reçu
    → Parse : MessageCreated / MessageDeleted / LabelChanged
    → Notifie toutes les IMAPSession en IDLE via asyncio.Event
    → Client reçoit "* N EXISTS" sans délai
```

## Stories détail

### S5-01 — Proton EventLoop

- `src/event_loop.py` — classe `ProtonEventLoop`
- Poll `GET /core/v4/events/{last_event_id}` en boucle
- Parse champs : `Messages`, `Labels`, `EventID`
- Publie sur `asyncio.Queue` pour consommateurs (IDLE sessions)
- Reconnexion auto si poll échoue

### S5-02 — Mapping event → IMAP push

- `MessageCreated` → `* N EXISTS` sur mailbox concernée
- `MessageDeleted` → `* N EXPUNGE`
- `LabelChanged` → invalide cache + `* N EXISTS`
- `MultiAccountBridge` expose `subscribe(mailbox, queue)` / `unsubscribe()`

### S5-03 — IDLE event-driven

- `_cmd_idle` attend sur `asyncio.Queue` au lieu de polling timer
- Timeout 29 min inchangé (RFC)
- DONE → unsubscribe queue + réponse OK
