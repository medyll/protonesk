import { describe, it, expect } from "vitest";
import * as imap from "../../src/mail/imap.js";

// Runs against the real hydroxide bridge (HYDROXIDE_* in .env). Read-only —
// no mailbox state is changed.
describe("hydroxide bridge (read-only)", () => {
  it("lists mailboxes including INBOX", async () => {
    const mailboxes = await imap.listMailboxes();
    expect(mailboxes.map((m) => m.path)).toContain("INBOX");
  });

  it("lists recent INBOX messages", async () => {
    const messages = await imap.listMessages("INBOX", { limit: 5 });
    expect(Array.isArray(messages)).toBe(true);
    for (const m of messages) {
      expect(typeof m.uid).toBe("number");
    }
  });

  it("fetches the full content of the most recent message", async () => {
    const [latest] = await imap.listMessages("INBOX", { limit: 1 });
    if (!latest) return; // empty mailbox

    const full = await imap.getMessage("INBOX", latest.uid);
    expect(full).not.toBeNull();
    expect(full?.uid).toBe(latest.uid);
    expect(Array.isArray(full?.attachments)).toBe(true);
  });

  it("searches INBOX for unseen messages", async () => {
    const results = await imap.searchMessages("INBOX", { unseen: true });
    expect(Array.isArray(results)).toBe(true);
  });
});
