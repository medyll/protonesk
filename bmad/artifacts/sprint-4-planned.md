# Sprint 4 — Multi-compte

**Goal:** Gérer plusieurs comptes Proton simultanément depuis un seul bridge.

## Stories

| ID | Titre | Effort |
|----|-------|--------|
| S4-01 | Config multi-compte dans config.yaml | S |
| S4-02 | Session manager — pool de sessions Proton | M |
| S4-03 | IMAP namespace par compte (INBOX/compte1, INBOX/compte2) | M |
| S4-04 | SMTP routing par expéditeur (From: → bon compte) | M |
| S4-05 | Reconnexion indépendante par compte | S |

## Design

```yaml
# config.yaml
accounts:
  - username: user1@proton.me
    label: perso
  - username: user2@proton.me
    label: pro
```

```
IMAP mailboxes exposées :
  perso/INBOX
  perso/Sent
  pro/INBOX
  pro/Sent
```

## Contraintes

- Chaque compte = session Proton indépendante + credentials keyring séparés
- `ProtonIMAPBridge` devient `MultiAccountBridge` avec dict `{label: bridge}`
- SMTP : `From:` header détermine quel compte envoie
- Reconnexion d'un compte n'affecte pas les autres
