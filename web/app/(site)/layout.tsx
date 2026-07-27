// Marketing site layout (Wave 3 stage 5, Claude Design incorporation).
// Loads the design system + site styles and wraps every page in the
// .sn-site scope so the design tokens stay isolated from the internal app.
// Fonts load at runtime per the handoff's design-system/fonts.html snippet.
// STAGED-DARK: the root layout's robots noindex applies to every page here;
// while PORTAL_ENABLED is off the gate keeps these routes auth-walled.
import "../design-system/tokens.css";
import "./site.css";
import SiteInteractions from "@/components/site/SiteInteractions";

export default function SiteLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="sn-site">
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        rel="preconnect"
        href="https://fonts.gstatic.com"
        crossOrigin="anonymous"
      />
      <link
        href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
        rel="stylesheet"
      />
      {children}
      <SiteInteractions />
    </div>
  );
}
