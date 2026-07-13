import { redirect } from "next/navigation";

// Middleware sends unauthenticated users to /login; everyone else lands on the
// review queue.
export default function Home() {
  redirect("/corpus");
}
