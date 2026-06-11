import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import * as imap from "./mail/imap.js";
import { sendMessage } from "./mail/smtp.js";

function jsonResult(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export function registerTools(server: McpServer): void {
  server.registerTool(
    "list_folders",
    {
      title: "List mail folders",
      description: "List all IMAP mailboxes/folders available in the account.",
      inputSchema: {},
    },
    async () => jsonResult(await imap.listMailboxes())
  );

  server.registerTool(
    "list_messages",
    {
      title: "List messages",
      description: "List messages in a mailbox, newest first.",
      inputSchema: {
        mailbox: z.string().describe("Mailbox path, e.g. INBOX"),
        limit: z.number().int().positive().max(100).optional().describe("Max messages to return (default 20)"),
        offset: z.number().int().min(0).optional().describe("Number of newest messages to skip (default 0)"),
      },
    },
    async ({ mailbox, limit, offset }) => jsonResult(await imap.listMessages(mailbox, { limit, offset }))
  );

  server.registerTool(
    "get_message",
    {
      title: "Get message",
      description: "Fetch a single message's full content (headers, text/html body, attachment metadata).",
      inputSchema: {
        mailbox: z.string().describe("Mailbox path, e.g. INBOX"),
        uid: z.number().int().positive().describe("Message UID"),
      },
    },
    async ({ mailbox, uid }) => {
      const msg = await imap.getMessage(mailbox, uid);
      if (!msg) {
        return { content: [{ type: "text" as const, text: `Message ${uid} not found in ${mailbox}` }], isError: true };
      }
      return jsonResult(msg);
    }
  );

  server.registerTool(
    "search_messages",
    {
      title: "Search messages",
      description: "Search messages in a mailbox by sender, recipient, subject, body text, date range, or flags.",
      inputSchema: {
        mailbox: z.string().describe("Mailbox path, e.g. INBOX"),
        from: z.string().optional().describe("Filter by sender address/name"),
        to: z.string().optional().describe("Filter by recipient address/name"),
        subject: z.string().optional().describe("Filter by subject substring"),
        text: z.string().optional().describe("Filter by body text substring"),
        since: z.string().optional().describe("ISO date; only messages on/after this date"),
        before: z.string().optional().describe("ISO date; only messages before this date"),
        unseen: z.boolean().optional().describe("Only unread messages"),
        flagged: z.boolean().optional().describe("Only flagged/starred messages"),
      },
    },
    async ({ mailbox, ...criteria }) => jsonResult(await imap.searchMessages(mailbox, criteria))
  );

  server.registerTool(
    "send_message",
    {
      title: "Send message",
      description: "Send an email via SMTP.",
      inputSchema: {
        to: z.string().describe("Recipient address(es), comma-separated"),
        cc: z.string().optional(),
        bcc: z.string().optional(),
        subject: z.string(),
        text: z.string().optional().describe("Plain text body"),
        html: z.string().optional().describe("HTML body"),
        inReplyTo: z.string().optional().describe("Message-ID being replied to"),
        references: z.string().optional().describe("References header for threading"),
      },
    },
    async (input) => jsonResult(await sendMessage(input))
  );

  server.registerTool(
    "mark_message",
    {
      title: "Mark message",
      description: "Set or clear a flag (seen, flagged, answered, draft, deleted) on a message.",
      inputSchema: {
        mailbox: z.string(),
        uid: z.number().int().positive(),
        flag: z.enum(["seen", "flagged", "answered", "draft", "deleted"]),
        value: z.boolean().describe("true to set the flag, false to clear it"),
      },
    },
    async ({ mailbox, uid, flag, value }) => {
      await imap.setFlag(mailbox, uid, flag, value);
      return jsonResult({ ok: true });
    }
  );

  server.registerTool(
    "move_message",
    {
      title: "Move message",
      description: "Move a message to another mailbox/folder.",
      inputSchema: {
        mailbox: z.string().describe("Source mailbox path"),
        uid: z.number().int().positive(),
        destination: z.string().describe("Destination mailbox path"),
      },
    },
    async ({ mailbox, uid, destination }) => {
      await imap.moveMessage(mailbox, uid, destination);
      return jsonResult({ ok: true });
    }
  );

  server.registerTool(
    "delete_message",
    {
      title: "Delete message",
      description: "Permanently delete a message (sets \\Deleted and expunges).",
      inputSchema: {
        mailbox: z.string(),
        uid: z.number().int().positive(),
      },
    },
    async ({ mailbox, uid }) => {
      await imap.deleteMessage(mailbox, uid);
      return jsonResult({ ok: true });
    }
  );
}
