import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

// Resolve .env from the package root, not process.cwd(). The server is launched by
// MCP clients whose cwd is the user's current project, so a bare `dotenv/config`
// never finds it — which is why the credentials used to be inlined in each client's
// config instead. Keep them in this one .env file.
const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
dotenv.config({ path: path.join(packageRoot, ".env") });

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
