import nodemailer from "nodemailer";
import { config } from "../config.js";

const transport = nodemailer.createTransport({
  host: config.host,
  port: config.smtpPort,
  secure: false,
  requireTLS: true,
  auth: { user: config.user, pass: config.password },
  tls: { rejectUnauthorized: false },
});

export interface SendMessageInput {
  to: string;
  cc?: string;
  bcc?: string;
  subject: string;
  text?: string;
  html?: string;
  inReplyTo?: string;
  references?: string;
}

export interface SendMessageResult {
  messageId: string;
  accepted: string[];
  rejected: string[];
}

export async function sendMessage(input: SendMessageInput): Promise<SendMessageResult> {
  const info = await transport.sendMail({
    from: config.user,
    to: input.to,
    cc: input.cc,
    bcc: input.bcc,
    subject: input.subject,
    text: input.text,
    html: input.html,
    inReplyTo: input.inReplyTo,
    references: input.references,
  });

  return {
    messageId: info.messageId,
    accepted: info.accepted.map(String),
    rejected: info.rejected.map(String),
  };
}
