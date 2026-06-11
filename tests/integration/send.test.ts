import { describe, it, expect } from "vitest";
import { sendMessage } from "../../src/mail/smtp.js";
import * as imap from "../../src/mail/imap.js";
import { config } from "../../src/config.js";

// Sends one real, self-addressed email and removes it from Sent afterwards.
// Opt-in only — set RUN_SEND_TEST=1 to avoid generating real traffic on
// every run.
const RUN = process.env.RUN_SEND_TEST === "1";

describe.skipIf(!RUN)("hydroxide bridge (send + cleanup, opt-in)", () => {
  it("sends a self-addressed test email and removes it from Sent", async () => {
    const marker = `protonesk-mcp-test-${Date.now()}`;

    const result = await sendMessage({
      to: config.user,
      subject: marker,
      text: "Integration test message from protonesk-mail-mcp. Safe to delete.",
    });
    expect(result.accepted).toContain(config.user);

    // Best-effort cleanup: hydroxide appends sent mail to "Sent" — find it
    // and delete it so the test leaves no trace.
    for (let i = 0; i < 10; i++) {
      const found = await imap.searchMessages("Sent", { subject: marker });
      if (found.length > 0) {
        await imap.deleteMessage("Sent", found[0].uid);
        return;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  });
});
