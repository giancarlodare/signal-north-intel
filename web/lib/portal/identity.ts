// Member display identity for the dashboard header (Claude Design fields
// member-initials / member-shortname). Honest derivation only: a provisioned
// full_name renders as initials + short name; otherwise the email local part
// stands in. Nothing is invented.

export interface MemberIdentity {
  initials: string;
  shortname: string;
}

export function memberIdentity(
  email: string | null | undefined,
  fullName?: string | null,
): MemberIdentity {
  const name = (fullName ?? "").trim();
  if (name) {
    const parts = name.split(/\s+/);
    const initials = parts
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? "")
      .join("");
    // "Morgan Chen" -> "M. Chen"; a single name renders as itself.
    const shortname =
      parts.length > 1
        ? `${parts[0][0].toUpperCase()}. ${parts[parts.length - 1]}`
        : name;
    return { initials: initials || "?", shortname };
  }
  const local = (email ?? "").split("@")[0];
  if (!local) return { initials: "?", shortname: "Member" };
  return { initials: local.slice(0, 2).toUpperCase(), shortname: local };
}
