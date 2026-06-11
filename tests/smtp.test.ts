import { describe, it, expect, vi, beforeEach } from "vitest";

const sendMail = vi.fn();

vi.mock("nodemailer", () => ({
  default: {
    createTransport: vi.fn(() => ({ sendMail })),
  },
}));

const nodemailer = (await import("nodemailer")).default;
const { sendMessage } = await import("../src/mail/smtp.js");

// Captured before beforeEach() clears mock history — the transport is
// created once at module-load time.
const transportConfig = vi.mocked(nodemailer.createTransport).mock.calls[0]?.[0];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("sendMessage", () => {
  it("creates a STARTTLS transport against the configured hydroxide SMTP endpoint", () => {
    expect(transportConfig).toEqual(
      expect.objectContaining({
        host: "127.0.0.1",
        port: 1025,
        secure: false,
        requireTLS: true,
        auth: { user: "test@proton.me", pass: "test-bridge-password" },
        tls: { rejectUnauthorized: false },
      })
    );
  });

  it("sends from the configured account and returns a normalized result", async () => {
    sendMail.mockResolvedValue({
      messageId: "<abc@proton.me>",
      accepted: ["to@example.com"],
      rejected: [],
    });

    const result = await sendMessage({
      to: "to@example.com",
      cc: "cc@example.com",
      subject: "Hello",
      text: "Hi there",
      html: "<p>Hi there</p>",
      inReplyTo: "<parent@proton.me>",
      references: "<parent@proton.me>",
    });

    expect(sendMail).toHaveBeenCalledWith({
      from: "test@proton.me",
      to: "to@example.com",
      cc: "cc@example.com",
      bcc: undefined,
      subject: "Hello",
      text: "Hi there",
      html: "<p>Hi there</p>",
      inReplyTo: "<parent@proton.me>",
      references: "<parent@proton.me>",
    });
    expect(result).toEqual({
      messageId: "<abc@proton.me>",
      accepted: ["to@example.com"],
      rejected: [],
    });
  });

  it("stringifies non-string accepted/rejected entries", async () => {
    sendMail.mockResolvedValue({
      messageId: "<abc@proton.me>",
      accepted: [{ address: "to@example.com" }],
      rejected: [{ address: "bad@example.com" }],
    });

    const result = await sendMessage({ to: "to@example.com", subject: "Hi" });

    expect(result.accepted).toEqual(["[object Object]"]);
    expect(result.rejected).toEqual(["[object Object]"]);
  });
});
