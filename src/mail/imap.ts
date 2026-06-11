import { ImapFlow, type ListResponse } from "imapflow";
import { simpleParser } from "mailparser";
import { config } from "../config.js";

function client(): ImapFlow {
  return new ImapFlow({
    host: config.host,
    port: config.imapPort,
    secure: false,
    tls: { rejectUnauthorized: false },
    auth: { user: config.user, pass: config.password },
    logger: false,
  });
}

async function withClient<T>(fn: (c: ImapFlow) => Promise<T>): Promise<T> {
  const c = client();
  await c.connect();
  try {
    return await fn(c);
  } finally {
    await c.logout();
  }
}

export interface MailboxSummary {
  path: string;
  name: string;
  delimiter: string;
  flags: string[];
  specialUse?: string;
}

export async function listMailboxes(): Promise<MailboxSummary[]> {
  return withClient(async (c) => {
    const list = await c.list();
    return list.map((box: ListResponse) => ({
      path: box.path,
      name: box.name,
      delimiter: box.delimiter,
      flags: Array.from(box.flags ?? []),
      specialUse: box.specialUse,
    }));
  });
}

export interface MessageSummary {
  uid: number;
  subject?: string;
  from?: string;
  to?: string;
  date?: string;
  flags: string[];
}

function envelopeAddresses(addrs?: { name?: string; address?: string }[]): string | undefined {
  if (!addrs || addrs.length === 0) return undefined;
  return addrs
    .map((a) => (a.name ? `${a.name} <${a.address}>` : a.address))
    .join(", ");
}

export async function listMessages(
  mailbox: string,
  opts: { limit?: number; offset?: number } = {}
): Promise<MessageSummary[]> {
  const limit = opts.limit ?? 20;
  const offset = opts.offset ?? 0;

  return withClient(async (c) => {
    const box = await c.mailboxOpen(mailbox, { readOnly: true });
    const total = box.exists;
    if (total === 0) return [];

    const end = total - offset;
    if (end < 1) return [];
    const start = Math.max(1, end - limit + 1);

    const messages: MessageSummary[] = [];
    for await (const msg of c.fetch(`${start}:${end}`, { envelope: true, flags: true, uid: true })) {
      messages.push({
        uid: msg.uid,
        subject: msg.envelope?.subject,
        from: envelopeAddresses(msg.envelope?.from),
        to: envelopeAddresses(msg.envelope?.to),
        date: msg.envelope?.date?.toISOString(),
        flags: Array.from(msg.flags ?? []),
      });
    }
    return messages.reverse();
  });
}

export interface FullMessage {
  uid: number;
  subject?: string;
  from?: string;
  to?: string;
  cc?: string;
  date?: string;
  text?: string;
  html?: string;
  attachments: { filename?: string; contentType: string; size: number }[];
}

export async function getMessage(mailbox: string, uid: number): Promise<FullMessage | null> {
  return withClient(async (c) => {
    await c.mailboxOpen(mailbox, { readOnly: true });
    const msg = await c.fetchOne(String(uid), { source: true, envelope: true }, { uid: true });
    if (!msg || !msg.source) return null;

    const parsed = await simpleParser(msg.source);
    return {
      uid: msg.uid,
      subject: parsed.subject,
      from: parsed.from?.text,
      to: parsed.to ? (Array.isArray(parsed.to) ? parsed.to.map((t) => t.text).join(", ") : parsed.to.text) : undefined,
      cc: parsed.cc ? (Array.isArray(parsed.cc) ? parsed.cc.map((c2) => c2.text).join(", ") : parsed.cc.text) : undefined,
      date: parsed.date?.toISOString(),
      text: parsed.text,
      html: typeof parsed.html === "string" ? parsed.html : undefined,
      attachments: parsed.attachments.map((a) => ({
        filename: a.filename,
        contentType: a.contentType,
        size: a.size,
      })),
    };
  });
}

export interface SearchCriteria {
  from?: string;
  to?: string;
  subject?: string;
  text?: string;
  since?: string;
  before?: string;
  unseen?: boolean;
  flagged?: boolean;
}

export async function searchMessages(mailbox: string, criteria: SearchCriteria): Promise<MessageSummary[]> {
  return withClient(async (c) => {
    await c.mailboxOpen(mailbox, { readOnly: true });

    const query: Record<string, unknown> = {};
    if (criteria.from) query.from = criteria.from;
    if (criteria.to) query.to = criteria.to;
    if (criteria.subject) query.subject = criteria.subject;
    if (criteria.text) query.body = criteria.text;
    if (criteria.since) query.since = new Date(criteria.since);
    if (criteria.before) query.before = new Date(criteria.before);
    if (criteria.unseen) query.seen = false;
    if (criteria.flagged) query.flagged = true;

    const uids = await c.search(query, { uid: true });
    if (!uids || uids.length === 0) return [];

    const messages: MessageSummary[] = [];
    for await (const msg of c.fetch(uids, { envelope: true, flags: true, uid: true }, { uid: true })) {
      messages.push({
        uid: msg.uid,
        subject: msg.envelope?.subject,
        from: envelopeAddresses(msg.envelope?.from),
        to: envelopeAddresses(msg.envelope?.to),
        date: msg.envelope?.date?.toISOString(),
        flags: Array.from(msg.flags ?? []),
      });
    }
    return messages.reverse();
  });
}

const FLAG_MAP: Record<string, string> = {
  seen: "\\Seen",
  flagged: "\\Flagged",
  deleted: "\\Deleted",
  answered: "\\Answered",
  draft: "\\Draft",
};

export async function setFlag(mailbox: string, uid: number, flag: string, value: boolean): Promise<void> {
  const imapFlag = FLAG_MAP[flag];
  if (!imapFlag) {
    throw new Error(`Unknown flag: ${flag}`);
  }

  await withClient(async (c) => {
    await c.mailboxOpen(mailbox);
    if (value) {
      await c.messageFlagsAdd(String(uid), [imapFlag], { uid: true });
    } else {
      await c.messageFlagsRemove(String(uid), [imapFlag], { uid: true });
    }
  });
}

export async function moveMessage(mailbox: string, uid: number, destination: string): Promise<void> {
  await withClient(async (c) => {
    await c.mailboxOpen(mailbox);
    await c.messageMove(String(uid), destination, { uid: true });
  });
}

export async function deleteMessage(mailbox: string, uid: number): Promise<void> {
  const c = client();
  await c.connect();
  try {
    await c.mailboxOpen(mailbox);
    await c.messageFlagsAdd(String(uid), ["\\Deleted"], { uid: true });
    // CLOSE permanently expunges messages flagged \Deleted (RFC 3501).
    await c.mailboxClose();
  } finally {
    await c.logout();
  }
}
