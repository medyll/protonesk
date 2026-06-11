// Fixed test config so dotenv (loaded by src/config.ts) never overrides these
// and tests never touch a real Proton account.
process.env.HYDROXIDE_HOST = "127.0.0.1";
process.env.HYDROXIDE_IMAP_PORT = "1143";
process.env.HYDROXIDE_SMTP_PORT = "1025";
process.env.HYDROXIDE_USER = "test@proton.me";
process.env.HYDROXIDE_PASSWORD = "test-bridge-password";
