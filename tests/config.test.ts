import { describe, it, expect, afterEach, vi } from "vitest";

// Avoid loading the real .env (it has real credentials) so these tests can
// freely add/remove HYDROXIDE_* vars without leaking real values.
vi.mock("dotenv/config", () => ({}));

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
  vi.resetModules();
});

describe("config", () => {
  it("defaults host/ports when not set", async () => {
    delete process.env.HYDROXIDE_HOST;
    delete process.env.HYDROXIDE_IMAP_PORT;
    delete process.env.HYDROXIDE_SMTP_PORT;

    const { config } = await import("../src/config.js");

    expect(config.host).toBe("127.0.0.1");
    expect(config.imapPort).toBe(1143);
    expect(config.smtpPort).toBe(1025);
    expect(config.user).toBe("test@proton.me");
    expect(config.password).toBe("test-bridge-password");
  });

  it("reads host/ports/credentials from env when set", async () => {
    process.env.HYDROXIDE_HOST = "10.0.0.5";
    process.env.HYDROXIDE_IMAP_PORT = "2143";
    process.env.HYDROXIDE_SMTP_PORT = "2025";
    process.env.HYDROXIDE_USER = "me@proton.me";
    process.env.HYDROXIDE_PASSWORD = "secret";

    const { config } = await import("../src/config.js");

    expect(config).toEqual({
      host: "10.0.0.5",
      imapPort: 2143,
      smtpPort: 2025,
      user: "me@proton.me",
      password: "secret",
    });
  });

  it("throws when HYDROXIDE_USER is missing", async () => {
    delete process.env.HYDROXIDE_USER;

    await expect(import("../src/config.js")).rejects.toThrow("HYDROXIDE_USER");
  });

  it("throws when HYDROXIDE_PASSWORD is missing", async () => {
    delete process.env.HYDROXIDE_PASSWORD;

    await expect(import("../src/config.js")).rejects.toThrow("HYDROXIDE_PASSWORD");
  });
});
