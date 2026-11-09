import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { createTokenSession, deleteTokenSession } from "@/lib/token-store";

const localAuthEnabled =
  process.env.APP_ENV === "development" && Boolean(process.env.DEVELOPMENT_AUTH_TOKEN);
const oidcIssuer = process.env.AUTH_OIDC_ISSUER;
const oidcClientId = process.env.AUTH_OIDC_CLIENT_ID;
const oidcClientSecret = process.env.AUTH_OIDC_CLIENT_SECRET;
const oidcEnabled = Boolean(oidcIssuer && oidcClientId && oidcClientSecret);
const authSecret = process.env.AUTH_SECRET;

if (process.env.APP_ENV === "production") {
  if (!authSecret || authSecret.length < 32) throw new Error("AUTH_SECRET must contain at least 32 characters in production");
  if (!process.env.AUTH_REDIS_URL) throw new Error("AUTH_REDIS_URL is required in production");
  if (!process.env.AUTH_REDIS_URL.startsWith("rediss://")) {
    throw new Error("AUTH_REDIS_URL must use TLS in production");
  }
  if (!process.env.AUTH_URL?.startsWith("https://")) {
    throw new Error("AUTH_URL must use HTTPS in production");
  }
  if (!oidcEnabled || !oidcIssuer?.startsWith("https://")) {
    throw new Error("A configured HTTPS OIDC provider is required in production");
  }
  if (!process.env.AUTH_OIDC_TOKEN_ENDPOINT?.startsWith("https://")) {
    throw new Error("A HTTPS AUTH_OIDC_TOKEN_ENDPOINT is required in production");
  }
}

const providers = [
  ...(oidcEnabled
    ? [
        {
          id: "oidc",
          name: "Sign in",
          type: "oidc" as const,
          issuer: oidcIssuer!,
          clientId: oidcClientId!,
          clientSecret: oidcClientSecret!,
          authorization: {
            params: {
              scope: process.env.AUTH_OIDC_SCOPE ?? "openid profile email offline_access",
              ...(process.env.AUTH_OIDC_AUDIENCE
                ? { audience: process.env.AUTH_OIDC_AUDIENCE }
                : {}),
            },
          },
          profile(profile: { sub: string }) {
            return { id: profile.sub };
          },
        },
      ]
    : []),
  ...(localAuthEnabled
    ? [
        Credentials({
          id: "local-development",
          name: "Local development",
          credentials: {},
          async authorize() {
            return {
              id: "local-developer",
              apiAccessToken: process.env.DEVELOPMENT_AUTH_TOKEN,
            };
          },
        }),
      ]
    : []),
];

export const authProviderEnabled = oidcEnabled || localAuthEnabled;
export const preferredProvider = oidcEnabled ? "oidc" : "local-development";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  secret: authSecret,
  trustHost: process.env.AUTH_TRUST_HOST === "true",
  session: { strategy: "jwt", maxAge: 30 * 60 },
  callbacks: {
    async jwt({ token, account, user }) {
      if (account?.access_token) {
        token.webSessionId = await createTokenSession({
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at ? account.expires_at * 1000 : Date.now() + 5 * 60 * 1000,
        });
      } else if (user && "apiAccessToken" in user && typeof user.apiAccessToken === "string") {
        token.webSessionId = await createTokenSession({
          accessToken: user.apiAccessToken,
          expiresAt: Date.now() + 30 * 60 * 1000,
        });
      }
      return token;
    },
  },
  events: {
    async signOut(message) {
      if ("token" in message) await deleteTokenSession(message.token?.webSessionId);
    },
  },
});
