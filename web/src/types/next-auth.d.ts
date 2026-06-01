import type { DefaultSession } from "next-auth";

export interface BrewingWorkspace {
  id: string;
  name: string;
  org_name?: string | null;
  operational_type?: string | null;
  subscription_tier?: string;
  onboarding_completed?: boolean;
  governance_require_auditor?: boolean;
  governance_human_authoritative?: boolean;
  treasury_address?: string | null;
  treasury_blockchain?: string | null;
}

declare module "next-auth" {
  interface Session {
    brewingToken?: string;
    role?: string;
    workspace?: BrewingWorkspace;
    user?: {
      id?: string;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    brewingToken?: string;
    role?: string;
    workspace?: BrewingWorkspace;
    userId?: string;
  }
}
