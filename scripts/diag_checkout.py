"""DIAG CHECKOUT: read-only diagnosis of what the checkout-first flow did for one
email address. Answers, from the rows themselves: did the webhook provision an
account, did a member_subscriptions row land, is there a provisioning_failures
row, and what is the free-list state. Writes nothing.

The welcome email is NOT visible here (that is a send, not a row); this reports
the entitlement state, which is what tells us whether "no welcome" is the
MEMBER_WELCOME_LIVE flag working as designed (row present, no failure) or a
genuine live-path divergence (no row / a failure row).

Usage:  diag_checkout.py <email>
"""
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""


def req(path):
    r = urllib.request.Request(
        BASE + path,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)


def find_user(email):
    """GoTrue admin list, paged, filtered by email (no reliable server-side
    email filter across versions, so we page and match)."""
    page = 1
    while page <= 20:
        data = req(f"/auth/v1/admin/users?page={page}&per_page=200")
        users = data.get("users") if isinstance(data, dict) else data
        if not users:
            return None
        for u in users:
            if (u.get("email") or "").lower() == email:
                return u
        if len(users) < 200:
            return None
        page += 1
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: diag_checkout.py <email>")
        return 2
    email = sys.argv[1].strip().lower()
    q = urllib.parse.quote(email)
    print(f"DIAG CHECKOUT for {email}\n" + "=" * 70)

    user = find_user(email)
    if user:
        print(f"AUTH USER: {user['id']}")
        print(f"  email            : {user.get('email')}")
        print(f"  created_at       : {user.get('created_at')}")
        print(f"  email_confirmed  : {user.get('email_confirmed_at') or user.get('confirmed_at')}")
        print(f"  last_sign_in_at  : {user.get('last_sign_in_at')}")
        subs = req(f"/rest/v1/member_subscriptions?member_id=eq.{user['id']}&select=*")
        print(f"MEMBER_SUBSCRIPTIONS ({len(subs)}):")
        for s in subs:
            print("  " + json.dumps({k: s.get(k) for k in
                  ("tier", "interval", "status", "current_period_end",
                   "stripe_subscription_id", "event_created_at")}))
        if not subs:
            print("  (none)")
    else:
        print("AUTH USER: NONE (no account was provisioned for this address)")

    pf = req(f"/rest/v1/provisioning_failures?email=eq.{q}&select=*")
    print(f"PROVISIONING_FAILURES ({len(pf)}):")
    for f in pf:
        print("  " + json.dumps({k: f.get(k) for k in
              ("reason", "tier", "interval", "stripe_subscription_id",
               "first_seen_at", "alerted_at", "resolved_at")}))
    if not pf:
        print("  (none)")

    bs = req(f"/rest/v1/brief_signups?email=eq.{q}&select=email,unsubscribed_at,created_at")
    print(f"BRIEF_SIGNUPS ({len(bs)}): {json.dumps(bs)}")

    print("\nREAD:")
    if user and req(f"/rest/v1/member_subscriptions?member_id=eq.{user['id']}&select=member_id"):
        print("  Account provisioned AND a subscription row landed. If no welcome")
        print("  arrived, that is MEMBER_WELCOME_LIVE=off holding the send (by")
        print("  design). The live path matched the E2E.")
    elif pf:
        print("  A provisioning_failures row exists: the live path hit a failure")
        print("  branch. Reason above; this is NOT the welcome flag.")
    elif user:
        print("  Account exists but NO subscription row: the orphan-account state")
        print("  (provisioned before an unmapped/failed price check).")
    else:
        print("  No account and no failure row: the webhook likely never reached")
        print("  provisioning (endpoint not pointed at this deployment, or the")
        print("  event was not delivered).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
