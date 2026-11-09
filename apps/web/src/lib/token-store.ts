import { createCipheriv, createDecipheriv, createHash, randomBytes, randomUUID } from "node:crypto";
import { createClient, type RedisClientType } from "redis";

const SESSION_TTL_SECONDS = 30 * 60;
const REFRESH_EARLY_MS = 60_000;
const LOCK_TTL_SECONDS = 10;

type TokenSet = {
  accessToken: string;
  refreshToken?: string;
  expiresAt: number;
};

let redis: RedisClientType | undefined;
let redisConnection: Promise<RedisClientType> | undefined;

function getRedisUrl(): string {
  const url = process.env.AUTH_REDIS_URL;
  if (!url) throw new Error("AUTH_REDIS_URL is required");
  return url;
}

async function getRedis(): Promise<RedisClientType> {
  if (redis?.isOpen) return redis;
  if (!redisConnection) {
    redis = createClient({ url: getRedisUrl() });
    redis.on("error", (error) => console.error("Auth session store connection error", error.name));
    redisConnection = redis.connect().then(() => redis!).catch((error: unknown) => {
      redisConnection = undefined;
      redis = undefined;
      throw error;
    });
  }
  return redisConnection;
}

function encryptionKey(): Buffer {
  const secret = process.env.AUTH_SECRET;
  if (!secret || secret.length < 32) throw new Error("AUTH_SECRET must contain at least 32 characters");
  return createHash("sha256").update(secret, "utf8").digest();
}

function encrypt(value: TokenSet): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const ciphertext = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  return [iv, cipher.getAuthTag(), ciphertext].map((part) => part.toString("base64url")).join(".");
}

function decrypt(value: string): TokenSet | null {
  try {
    const [ivPart, tagPart, ciphertextPart] = value.split(".");
    if (!ivPart || !tagPart || !ciphertextPart) return null;
    const decipher = createDecipheriv("aes-256-gcm", encryptionKey(), Buffer.from(ivPart, "base64url"));
    decipher.setAuthTag(Buffer.from(tagPart, "base64url"));
    const plaintext = Buffer.concat([
      decipher.update(Buffer.from(ciphertextPart, "base64url")),
      decipher.final(),
    ]).toString("utf8");
    const parsed: unknown = JSON.parse(plaintext);
    if (
      typeof parsed !== "object" || parsed === null ||
      typeof (parsed as TokenSet).accessToken !== "string" ||
      typeof (parsed as TokenSet).expiresAt !== "number"
    ) return null;
    return parsed as TokenSet;
  } catch {
    return null;
  }
}

function sessionKey(id: string): string {
  return `lablens:web-session:${id}`;
}

export async function createTokenSession(tokens: Omit<TokenSet, "expiresAt"> & { expiresAt?: number }): Promise<string> {
  const id = randomUUID();
  const record: TokenSet = { ...tokens, expiresAt: tokens.expiresAt ?? Date.now() + SESSION_TTL_SECONDS * 1000 };
  await (await getRedis()).set(sessionKey(id), encrypt(record), { EX: SESSION_TTL_SECONDS });
  return id;
}

async function load(id: string): Promise<TokenSet | null> {
  const redisClient = await getRedis();
  const value = await redisClient.get(sessionKey(id));
  if (!value) return null;
  const tokens = decrypt(value);
  if (!tokens) await redisClient.del(sessionKey(id));
  return tokens;
}

async function refresh(tokens: TokenSet): Promise<TokenSet | null> {
  const endpoint = process.env.AUTH_OIDC_TOKEN_ENDPOINT;
  const clientId = process.env.AUTH_OIDC_CLIENT_ID;
  const clientSecret = process.env.AUTH_OIDC_CLIENT_SECRET;
  if (!endpoint || !clientId || !clientSecret || !tokens.refreshToken) return null;
  const encodedClientCredentials = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
  }).toString();

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      authorization: `Basic ${Buffer.from(encodedClientCredentials).toString("base64")}`,
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: tokens.refreshToken,
    }),
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) return null;
  const result: unknown = await response.json();
  if (typeof result !== "object" || result === null || typeof (result as { access_token?: unknown }).access_token !== "string") return null;
  const body = result as { access_token: string; expires_in?: number; refresh_token?: string };
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token ?? tokens.refreshToken,
    expiresAt: Date.now() + Math.max(30, body.expires_in ?? 300) * 1000,
  };
}

export async function getValidAccessToken(id: string): Promise<string | null> {
  const client = await getRedis();
  const key = sessionKey(id);
  let tokens = await load(id);
  if (!tokens) return null;
  if (tokens.expiresAt > Date.now() + REFRESH_EARLY_MS) return tokens.accessToken;

  const lockKey = `${key}:refresh-lock`;
  const lockId = randomUUID();
  const locked = await client.set(lockKey, lockId, { NX: true, EX: LOCK_TTL_SECONDS });
  if (!locked) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      tokens = await load(id);
      if (!tokens || tokens.expiresAt > Date.now() + REFRESH_EARLY_MS) return tokens?.accessToken ?? null;
    }
    return null;
  }

  try {
    tokens = await load(id);
    if (!tokens) return null;
    if (tokens.expiresAt > Date.now() + REFRESH_EARLY_MS) return tokens.accessToken;
    const refreshed = await refresh(tokens);
    if (!refreshed) {
      await client.del(key);
      return null;
    }
    await client.set(key, encrypt(refreshed), { EX: SESSION_TTL_SECONDS });
    return refreshed.accessToken;
  } catch {
    return null;
  } finally {
    if (await client.get(lockKey) === lockId) await client.del(lockKey);
  }
}

export async function deleteTokenSession(id: string | undefined): Promise<void> {
  if (id) await (await getRedis()).del(sessionKey(id));
}
