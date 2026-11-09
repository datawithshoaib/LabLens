"use server";

import { preferredProvider, signIn, signOut } from "@/auth";

export async function signInAction() {
  await signIn(preferredProvider, { redirectTo: "/dashboard" });
}

export async function signOutAction() {
  await signOut({ redirectTo: "/" });
}
