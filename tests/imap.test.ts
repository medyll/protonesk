import { describe, it, expect, vi, beforeEach } from "vitest";
import { asyncIterable } from "./helpers.js";

const connect = vi.fn();
const logout = vi.fn();
const list = vi.fn();
const mailboxOpen = vi.fn();
const fetch = vi.fn();
const fetchOne = vi.fn();
const search = vi.fn();
const messageFlagsAdd = vi.fn();
const messageFlagsRemove = vi.fn();
const messageMove = vi.fn();
const mailboxClose = vi.fn();

vi.mock("imapflow", () => ({
  ImapFlow: vi.fn().mockImplementation(() => ({
    connect,
    logout,
    list,
    mailboxOpen,
    fetch,
    fetchOne,
    search,
    messageFlagsAdd,
    messageFlagsRemove,
    messageMove,
    mailboxClose,
  })),
}));

const { ImapFlow } = await import("imapflow");
const imap = await import("../src/mail/imap.js");

beforeEach(() => {
  vi.clearAllMocks();
  connect.mockResolvedValue(undefined);
  logout.mockResolvedValue(undefined);
});

describe("listMailboxes", () => {
  it("maps ImapFlow list() output, connects and logs out", async () => {
    list.mockResolvedValue([
      { path: "INBOX", name: "INBOX", delimiter: "/", flags: new Set(["\\Noinferiors"]), specialUse: "\\Inbox" },
      { path: "Sent", name: "Sent", delimiter: "/", flags: new Set(), specialUse: undefined },
    ]);

    const result = await imap.listMailboxes();

    expect(connect).toHaveBeenCalledTimes(1);
    expect(logout).toHaveBeenCalledTimes(1);
    expect(result).toEqual([
      { path: "INBOX", name: "INBOX", delimiter: "/", flags: ["\\Noinferiors"], specialUse: "\\Inbox" },
      { path: "Sent", name: "Sent", delimiter: "/", flags: [], specialUse: undefined },
    ]);
  });

  it("logs out even if the call fails", async () => {
    list.mockRejectedValue(new Error("boom"));

    await expect(imap.listMailboxes()).rejects.toThrow("boom");
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("connects with a fresh client using configured host/port/credentials", async () => {
    list.mockResolvedValue([]);
    await imap.listMailboxes();

    expect(ImapFlow).toHaveBeenCalledWith(
      expect.objectContaining({
        host: "127.0.0.1",
        port: 1143,
        secure: false,
        auth: { user: "test@proton.me", pass: "test-bridge-password" },
        tls: { rejectUnauthorized: false },
      })
    );
  });
});

describe("listMessages", () => {
  it("returns [] for an empty mailbox without fetching", async () => {
    mailboxOpen.mockResolvedValue({ exists: 0 });

    const result = await imap.listMessages("INBOX");

    expect(result).toEqual([]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns [] when offset skips past all messages", async () => {
    mailboxOpen.mockResolvedValue({ exists: 5 });

    const result = await imap.listMessages("INBOX", { offset: 10 });

    expect(result).toEqual([]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("fetches the newest `limit` messages, newest first", async () => {
    mailboxOpen.mockResolvedValue({ exists: 10 });
    fetch.mockReturnValue(
      asyncIterable([
        { uid: 8, envelope: { subject: "A", from: [{ address: "a@x.com" }], to: [], date: new Date("2024-01-01") }, flags: new Set() },
        { uid: 9, envelope: { subject: "B", from: [{ name: "Bob", address: "b@x.com" }], to: [], date: new Date("2024-01-02") }, flags: new Set(["\\Seen"]) },
        { uid: 10, envelope: { subject: "C", from: [], to: [], date: new Date("2024-01-03") }, flags: new Set() },
      ])
    );

    const result = await imap.listMessages("INBOX", { limit: 3 });

    expect(mailboxOpen).toHaveBeenCalledWith("INBOX", { readOnly: true });
    expect(fetch).toHaveBeenCalledWith("8:10", { envelope: true, flags: true, uid: true });
    expect(result.map((m) => m.uid)).toEqual([10, 9, 8]);
    expect(result[2]).toEqual({
      uid: 8,
      subject: "A",
      from: "a@x.com",
      to: undefined,
      date: "2024-01-01T00:00:00.000Z",
      flags: [],
    });
    expect(result[1].from).toBe("Bob <b@x.com>");
    expect(result[1].flags).toEqual(["\\Seen"]);
  });

  it("clamps the start of the range to message 1", async () => {
    mailboxOpen.mockResolvedValue({ exists: 3 });
    fetch.mockReturnValue(asyncIterable([]));

    await imap.listMessages("INBOX", { limit: 20, offset: 0 });

    expect(fetch).toHaveBeenCalledWith("1:3", { envelope: true, flags: true, uid: true });
  });

  it("applies offset to skip the newest messages", async () => {
    mailboxOpen.mockResolvedValue({ exists: 10 });
    fetch.mockReturnValue(asyncIterable([]));

    await imap.listMessages("INBOX", { limit: 2, offset: 3 });

    // newest 3 skipped -> end = 7, start = 6
    expect(fetch).toHaveBeenCalledWith("6:7", { envelope: true, flags: true, uid: true });
  });
});

describe("getMessage", () => {
  it("returns null when the message doesn't exist", async () => {
    mailboxOpen.mockResolvedValue({});
    fetchOne.mockResolvedValue(undefined);

    const result = await imap.getMessage("INBOX", 999);

    expect(result).toBeNull();
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("parses the raw source into headers/text/attachments", async () => {
    mailboxOpen.mockResolvedValue({});
    const raw = [
      "From: Alice <alice@example.com>",
      "To: Bob <bob@example.com>",
      "Cc: Carol <carol@example.com>",
      "Subject: Hello",
      "Date: Mon, 01 Jan 2024 12:00:00 +0000",
      "Content-Type: text/plain; charset=utf-8",
      "",
      "Hello world",
      "",
    ].join("\r\n");

    fetchOne.mockResolvedValue({ uid: 42, source: Buffer.from(raw) });

    const result = await imap.getMessage("INBOX", 42);

    expect(mailboxOpen).toHaveBeenCalledWith("INBOX", { readOnly: true });
    expect(fetchOne).toHaveBeenCalledWith("42", { source: true, envelope: true }, { uid: true });
    expect(result).not.toBeNull();
    expect(result?.uid).toBe(42);
    expect(result?.subject).toBe("Hello");
    expect(result?.from).toBe('"Alice" <alice@example.com>');
    expect(result?.to).toBe('"Bob" <bob@example.com>');
    expect(result?.cc).toBe('"Carol" <carol@example.com>');
    expect(result?.text?.trim()).toBe("Hello world");
    expect(result?.attachments).toEqual([]);
  });
});

describe("searchMessages", () => {
  it("returns [] when nothing matches", async () => {
    mailboxOpen.mockResolvedValue({});
    search.mockResolvedValue([]);

    const result = await imap.searchMessages("INBOX", { unseen: true });

    expect(result).toEqual([]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("builds the IMAP search query and returns newest-first summaries", async () => {
    mailboxOpen.mockResolvedValue({});
    search.mockResolvedValue([3, 4]);
    fetch.mockReturnValue(
      asyncIterable([
        { uid: 3, envelope: { subject: "Old", from: [], to: [], date: new Date("2024-01-01") }, flags: new Set() },
        { uid: 4, envelope: { subject: "New", from: [], to: [], date: new Date("2024-01-02") }, flags: new Set(["\\Flagged"]) },
      ])
    );

    const result = await imap.searchMessages("INBOX", {
      from: "alice@example.com",
      to: "bob@example.com",
      subject: "invoice",
      text: "total",
      since: "2024-01-01T00:00:00.000Z",
      before: "2024-02-01T00:00:00.000Z",
      unseen: true,
      flagged: true,
    });

    expect(search).toHaveBeenCalledWith(
      {
        from: "alice@example.com",
        to: "bob@example.com",
        subject: "invoice",
        body: "total",
        since: new Date("2024-01-01T00:00:00.000Z"),
        before: new Date("2024-02-01T00:00:00.000Z"),
        seen: false,
        flagged: true,
      },
      { uid: true }
    );
    expect(fetch).toHaveBeenCalledWith([3, 4], { envelope: true, flags: true, uid: true }, { uid: true });
    expect(result.map((m) => m.uid)).toEqual([4, 3]);
  });

  it("omits unset criteria from the search query", async () => {
    mailboxOpen.mockResolvedValue({});
    search.mockResolvedValue([]);

    await imap.searchMessages("INBOX", { subject: "hi" });

    expect(search).toHaveBeenCalledWith({ subject: "hi" }, { uid: true });
  });
});

describe("setFlag", () => {
  it("rejects unknown flags without opening a connection", async () => {
    await expect(imap.setFlag("INBOX", 1, "bogus", true)).rejects.toThrow("Unknown flag: bogus");
    expect(connect).not.toHaveBeenCalled();
  });

  it("adds a flag when value is true", async () => {
    mailboxOpen.mockResolvedValue({});

    await imap.setFlag("INBOX", 7, "seen", true);

    expect(mailboxOpen).toHaveBeenCalledWith("INBOX");
    expect(messageFlagsAdd).toHaveBeenCalledWith("7", ["\\Seen"], { uid: true });
    expect(messageFlagsRemove).not.toHaveBeenCalled();
  });

  it("removes a flag when value is false", async () => {
    mailboxOpen.mockResolvedValue({});

    await imap.setFlag("INBOX", 7, "flagged", false);

    expect(messageFlagsRemove).toHaveBeenCalledWith("7", ["\\Flagged"], { uid: true });
    expect(messageFlagsAdd).not.toHaveBeenCalled();
  });
});

describe("moveMessage", () => {
  it("opens the source mailbox and moves by uid", async () => {
    mailboxOpen.mockResolvedValue({});

    await imap.moveMessage("INBOX", 12, "Archive");

    expect(mailboxOpen).toHaveBeenCalledWith("INBOX");
    expect(messageMove).toHaveBeenCalledWith("12", "Archive", { uid: true });
  });
});

describe("deleteMessage", () => {
  it("flags \\Deleted and closes the mailbox to expunge", async () => {
    mailboxOpen.mockResolvedValue({});
    mailboxClose.mockResolvedValue(undefined);

    await imap.deleteMessage("INBOX", 5);

    expect(mailboxOpen).toHaveBeenCalledWith("INBOX");
    expect(messageFlagsAdd).toHaveBeenCalledWith("5", ["\\Deleted"], { uid: true });
    expect(mailboxClose).toHaveBeenCalledTimes(1);
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("still logs out if flagging fails", async () => {
    mailboxOpen.mockResolvedValue({});
    messageFlagsAdd.mockRejectedValue(new Error("nope"));

    await expect(imap.deleteMessage("INBOX", 5)).rejects.toThrow("nope");
    expect(logout).toHaveBeenCalledTimes(1);
    expect(mailboxClose).not.toHaveBeenCalled();
  });
});
