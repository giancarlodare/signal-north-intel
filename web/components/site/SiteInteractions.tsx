"use client";
// Marketing site interactions, ported from the Claude Design handoff's
// js/site.js (vanilla, DOM-driven). Kept as one effect over the same
// selectors so the handoff file remains the reference: live-row expand, tab
// groups, capabilities selector, timeline scroll progress, request-access
// form gating with the handoff's mailto fallback (TODO in the handoff: swap
// for a pipeline endpoint when one exists), and single-select role chips.
// The handoff's login stub is NOT ported: /login is wired to real auth.
import { useEffect } from "react";

export default function SiteInteractions() {
  useEffect(() => {
    const cleanups: (() => void)[] = [];
    const on = (
      el: Element | Window,
      ev: string,
      fn: EventListenerOrEventListenerObject,
      opts?: AddEventListenerOptions
    ) => {
      el.addEventListener(ev, fn, opts);
      cleanups.push(() => el.removeEventListener(ev, fn, opts));
    };

    // Expand/collapse live rows
    document.querySelectorAll(".live-row").forEach((row) => {
      on(row, "click", () => {
        const open = row.classList.contains("is-open");
        document
          .querySelectorAll(".live-row.is-open")
          .forEach((r) => r.classList.remove("is-open"));
        if (!open) row.classList.add("is-open");
      });
    });

    // Generic tab groups: [data-tabs] contains .tab[data-panel]
    document.querySelectorAll("[data-tabs]").forEach((group) => {
      const name = group.getAttribute("data-tabs");
      group.querySelectorAll(".tab").forEach((tab) => {
        on(tab, "click", () => {
          group
            .querySelectorAll(".tab")
            .forEach((t) => t.classList.remove("is-active"));
          tab.classList.add("is-active");
          document
            .querySelectorAll(`[data-panel-group="${name}"]`)
            .forEach((p) => {
              (p as HTMLElement).hidden =
                p.getAttribute("data-panel") !== tab.getAttribute("data-panel");
            });
        });
      });
    });

    // Capabilities selector
    document.querySelectorAll(".caps").forEach((caps) => {
      caps.querySelectorAll(".caps__item").forEach((item) => {
        on(item, "click", () => {
          caps
            .querySelectorAll(".caps__item")
            .forEach((i) => i.classList.remove("is-active"));
          item.classList.add("is-active");
          caps.querySelectorAll("[data-cap-detail]").forEach((d) => {
            (d as HTMLElement).hidden =
              d.getAttribute("data-cap-detail") !== item.getAttribute("data-cap");
          });
        });
      });
    });

    // Scroll-driven vertical prediction timeline
    const arc = document.querySelector(".arc");
    if (arc) {
      const steps = arc.querySelectorAll(".arc__step");
      const dots = arc.querySelectorAll(".arc__dot");
      const trail = arc.querySelector(".arc__trail") as HTMLElement | null;
      const cursor = arc.querySelector(".arc__cursor") as HTMLElement | null;
      const onScroll = () => {
        const r = arc.getBoundingClientRect();
        const vh = window.innerHeight || 900;
        const prog = Math.max(
          0,
          Math.min(1, (vh * 0.78 - r.top) / Math.max(r.height, 1))
        );
        const travel = r.height - 106; // rail top 10px, dashed foot ~96px
        if (trail) trail.style.height = Math.min(prog, 0.8) * travel + "px";
        if (cursor) cursor.style.top = 10 + prog * travel + "px";
        steps.forEach((s, i) => {
          const isOn = prog >= (i + 0.5) / steps.length - 0.5 / steps.length;
          s.classList.toggle("is-on", isOn);
          if (dots[i]) dots[i].classList.toggle("is-on", isOn);
        });
      };
      on(window, "scroll", onScroll, { passive: true });
      onScroll();
    }

    // Request-access form: gate submit on name + organisation + valid email
    const form = document.querySelector(
      '[data-form="request-access"]'
    ) as HTMLFormElement | null;
    if (form) {
      const btn = form.querySelector("[data-submit]") as HTMLButtonElement;
      const hint = form.querySelector("[data-hint]");
      const field = (n: string) =>
        form.querySelector(`[name=${n}]`) as HTMLInputElement;
      const valid = () =>
        Boolean(
          field("name").value.trim() &&
            field("org").value.trim() &&
            /.+@.+\..+/.test(field("email").value)
        );
      const refresh = () => {
        btn.disabled = !valid();
        if (hint)
          hint.textContent = valid()
            ? "We reply within one business day."
            : "Name, organisation and a work email are all we need.";
      };
      on(form, "input", refresh);
      refresh();
      on(form, "submit", (e) => {
        e.preventDefault();
        if (!valid()) return;
        const f = (n: string) => encodeURIComponent(field(n).value);
        const role = form.querySelector(".chip.is-active");
        location.href =
          "mailto:giancarlo@signalnorthintel.com?subject=Access request - " +
          f("org") +
          "&body=Name: " +
          f("name") +
          "%0AOrganisation: " +
          f("org") +
          "%0AEmail: " +
          f("email") +
          "%0ATelephone: " +
          f("phone") +
          "%0ARole: " +
          encodeURIComponent(role ? role.textContent ?? "" : "") +
          "%0AScope: " +
          f("scope");
      });
    }

    // Role chips (single-select)
    document.querySelectorAll(".chip-row--select").forEach((row) => {
      row.querySelectorAll(".chip").forEach((chip) => {
        on(chip, "click", () => {
          row
            .querySelectorAll(".chip")
            .forEach((c) => c.classList.remove("is-active"));
          chip.classList.add("is-active");
        });
      });
    });

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return null;
}
