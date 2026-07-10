import { signIn } from "./actions";

export const dynamic = "force-dynamic";

export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string };
}) {
  return (
    <main className="wrap">
      <form action={signIn} className="login">
        <h1>Signal Review</h1>
        {searchParams.error ? <p className="err">{searchParams.error}</p> : null}
        <input
          name="email"
          type="email"
          placeholder="Email"
          autoComplete="username"
          required
        />
        <input
          name="password"
          type="password"
          placeholder="Password"
          autoComplete="current-password"
          required
        />
        <button className="approve" type="submit">
          Sign in
        </button>
      </form>
    </main>
  );
}
