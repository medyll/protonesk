import { describe, it, expect, vi, beforeEach } from "vitest";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const listMailboxes = vi.fn();
const listMessages = vi.fn();
const getMessage = vi.fn();
const searchMessages = vi.fn();
const setFlag = vi.fn();
const moveMessage = vi.fn();
const deleteMessage = vi.fn();

vi.mock("../src/mail/imap.js", () => ({
  listMailboxes,
  listMessages,
  getMessage,
  searchMessages,
  setFlag,
  moveMessage,
  deleteMessage,
}));

const sendMessage = vi.fn();
vi.mock("../src/mail/smtp.js", () => ({ sendMessage }));

const { registerTools } = await import("../src/tools.js");

type ToolHandler = (input: any) => Promise<{ content: { type: "text"; text: string }[]; isError?: boolean }>;

class FakeServer {
  tools = new Map<string, { def: unknown; handler: ToolHandler }>();
  registerTool(name: string, def: unknown, handler: ToolHandler) {
    this.tools.set(name, { def, handler });
  }
}

function setup() {
  const server = new FakeServer();
  registerTools(server as unknown as McpServer);
  return server;
}

beforeEach(() => {
  vi.clearAllMocks();
});

function jsonOf(result: { content: { type: "text"; text: string }[] }) {
  return JSON.parse(result.content[0].text);
}

describe("registerTools", () => {
  it("registers all 8 mail tools", () => {
    const server = setup();
    expect([...server.tools.keys()]).toEqual([
      "list_folders",
      "list_messages",
      "get_message",
      "search_messages",
      "send_message",
      "mark_message",
      "move_message",
      "delete_message",
    ]);
  });

  it("list_folders returns the mailbox list", async () => {
    const server = setup();
    listMailboxes.mockResolvedValue([{ path: "INBOX" }]);

    const result = await server.tools.get("list_folders")!.handler({});

    expect(listMailboxes).toHaveBeenCalled();
    expect(jsonOf(result)).toEqual([{ path: "INBOX" }]);
  });

  it("list_messages forwards mailbox/limit/offset", async () => {
    const server = setup();
    listMessages.mockResolvedValue([{ uid: 1 }]);

    const result = await server.tools.get("list_messages")!.handler({ mailbox: "INBOX", limit: 5, offset: 2 });

    expect(listMessages).toHaveBeenCalledWith("INBOX", { limit: 5, offset: 2 });
    expect(jsonOf(result)).toEqual([{ uid: 1 }]);
  });

  it("get_message returns the parsed message", async () => {
    const server = setup();
    getMessage.mockResolvedValue({ uid: 42, subject: "Hi" });

    const result = await server.tools.get("get_message")!.handler({ mailbox: "INBOX", uid: 42 });

    expect(getMessage).toHaveBeenCalledWith("INBOX", 42);
    expect(jsonOf(result)).toEqual({ uid: 42, subject: "Hi" });
    expect(result.isError).toBeUndefined();
  });

  it("get_message reports an error when the message is missing", async () => {
    const server = setup();
    getMessage.mockResolvedValue(null);

    const result = await server.tools.get("get_message")!.handler({ mailbox: "INBOX", uid: 999 });

    expect(result.isError).toBe(true);
    expect(result.content[0].text).toContain("999");
    expect(result.content[0].text).toContain("INBOX");
  });

  it("search_messages strips mailbox out of the criteria", async () => {
    const server = setup();
    searchMessages.mockResolvedValue([]);

    await server.tools.get("search_messages")!.handler({ mailbox: "INBOX", subject: "invoice", unseen: true });

    expect(searchMessages).toHaveBeenCalledWith("INBOX", { subject: "invoice", unseen: true });
  });

  it("send_message forwards the input to sendMessage", async () => {
    const server = setup();
    sendMessage.mockResolvedValue({ messageId: "<id@x>", accepted: ["a@b.com"], rejected: [] });

    const input = { to: "a@b.com", subject: "Hi", text: "hello" };
    const result = await server.tools.get("send_message")!.handler(input);

    expect(sendMessage).toHaveBeenCalledWith(input);
    expect(jsonOf(result)).toEqual({ messageId: "<id@x>", accepted: ["a@b.com"], rejected: [] });
  });

  it("mark_message sets a flag and acks", async () => {
    const server = setup();

    const result = await server.tools.get("mark_message")!.handler({ mailbox: "INBOX", uid: 7, flag: "seen", value: true });

    expect(setFlag).toHaveBeenCalledWith("INBOX", 7, "seen", true);
    expect(jsonOf(result)).toEqual({ ok: true });
  });

  it("move_message moves and acks", async () => {
    const server = setup();

    const result = await server.tools.get("move_message")!.handler({ mailbox: "INBOX", uid: 7, destination: "Archive" });

    expect(moveMessage).toHaveBeenCalledWith("INBOX", 7, "Archive");
    expect(jsonOf(result)).toEqual({ ok: true });
  });

  it("delete_message deletes and acks", async () => {
    const server = setup();

    const result = await server.tools.get("delete_message")!.handler({ mailbox: "INBOX", uid: 7 });

    expect(deleteMessage).toHaveBeenCalledWith("INBOX", 7);
    expect(jsonOf(result)).toEqual({ ok: true });
  });
});
