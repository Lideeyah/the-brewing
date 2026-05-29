import NextAuth, { type Session } from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";

const API = process.env.BREWING_API_URL ?? "http://localhost:8000";

/**
 * Web owns the sign-in UX. After a verified sign-in we exchange the identity
 * for a canonical Brewing session token issued by the API (the identity source
 * of truth). The shared SESSION_SECRET authenticates this server-to-server call
 * and never reaches the browser.
 */
async function exchangeBrewingSession(identity: {
  email: string;
  name?: string | null;
  image?: string | null;
}) {
  const res = await fetch(`${API}/auth/session`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Brewing-Auth": process.env.SESSION_SECRET ?? "",
    },
    body: JSON.stringify({
      email: identity.email,
      name: identity.name ?? null,
      image: identity.image ?? null,
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Brewing session exchange failed: ${res.status}`);
  }
  return res.json();
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  providers: [
    Google,
    // Dev/email sign-in: no SMTP required for local development. Authenticates
    // by email identity; the API still governs all authorization downstream.
    Credentials({
      id: "dev-email",
      name: "Email",
      credentials: { email: {}, name: {} },
      authorize: async (creds) => {
        const email = (creds?.email as string | undefined)?.trim();
        if (!email || !email.includes("@")) return null;
        const name =
          (creds?.name as string | undefined)?.trim() || email.split("@")[0];
        return { id: email, email, name };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // `user` is only present at initial sign-in — exchange exactly once.
      if (user?.email) {
        try {
          const s = await exchangeBrewingSession({
            email: user.email,
            name: user.name,
            image: (user as { image?: string | null }).image,
          });
          token.brewingToken = s.token;
          token.workspace = s.workspace;
          token.role = s.role;
          token.userId = s.user.id;
        } catch (err) {
          console.error("Brewing session exchange failed", err);
        }
      }
      return token;
    },
    async session({ session, token }) {
      const t = token as {
        brewingToken?: string;
        workspace?: Session["workspace"];
        role?: string;
        userId?: string;
      };
      session.brewingToken = t.brewingToken;
      session.workspace = t.workspace;
      session.role = t.role;
      if (session.user && t.userId) session.user.id = t.userId;
      return session;
    },
  },
});
