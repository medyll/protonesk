import "dotenv/config";

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const config = {
  host: process.env.HYDROXIDE_HOST ?? "127.0.0.1",
  imapPort: Number(process.env.HYDROXIDE_IMAP_PORT ?? 1143),
  smtpPort: Number(process.env.HYDROXIDE_SMTP_PORT ?? 1025),
  user: required("HYDROXIDE_USER"),
  password: required("HYDROXIDE_PASSWORD"),
};
