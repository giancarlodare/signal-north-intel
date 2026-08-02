// WHICH portal routes the paywall covers (operator standing rule 2026-08-01).
//
// THE DEADLOCK THIS AVOIDS: checkout lives at /portal/account. Guarding the
// whole member layout would mean an unsubscribed member cannot reach the page
// where they subscribe -- locked out of the door they need to walk through.
//
// So the portal splits in two:
//   RELATIONSHIP surface  /portal/account. Reachable by ANY authenticated
//                         member regardless of subscription. It is where
//                         checkout, billing state and sign-out live, and it
//                         is where an unpaid member is SENT, never blocked.
//   PRODUCT surface       everything else under /portal/*. Requires a paid-up
//                         subscription row.
//
// An unsubscribed member hitting a product route is REDIRECTED to the account
// page with an honest reason, not shown a 404. They are a real member who has
// not paid, and telling them so is both truthful and the only way they can
// act on it.
const RELATIONSHIP_PATHS = ["/portal/account"] as const;

export function isRelationshipPath(path: string): boolean {
  return (RELATIONSHIP_PATHS as readonly string[]).some(
    (p) => path === p || path.startsWith(p + "/"),
  );
}

// True when this path needs a paid-up row. Non-portal paths are not this
// function's business and answer false.
export function requiresSubscription(path: string): boolean {
  const inPortal = path === "/portal" || path.startsWith("/portal/");
  return inPortal && !isRelationshipPath(path);
}
