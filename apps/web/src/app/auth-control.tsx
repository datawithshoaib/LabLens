import Link from "next/link";

import { auth, authProviderEnabled } from "@/auth";
import { signInAction, signOutAction } from "@/app/actions";

export default async function AuthControl() {
  const session = await auth();
  if (session) {
    return (
      <div className="auth-actions">
        <Link className="top-link" href="/dashboard">My reports</Link>
        <form action={signOutAction}><button className="text-button" type="submit">Sign out</button></form>
      </div>
    );
  }
  if (!authProviderEnabled) {
    return <span className="auth-unavailable">Sign-in setup required</span>;
  }
  return (
    <form action={signInAction}>
      <button className="top-link top-button" type="submit">Sign in securely</button>
    </form>
  );
}
