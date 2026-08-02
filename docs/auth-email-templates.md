# Auth email templates — copy for operator approval

Status: PROPOSED 2026-08-02, folded into task #57 (custom SMTP on
mail.signalnorthintel.com gives one sender identity for auth mail and the
weekly brief). Nothing is configured in Supabase until the operator approves
this copy and the SMTP domain is live.

Sender for all auth mail: `Signal North <mail@signalnorthintel.com>` (or the
subdomain address the SMTP setup lands on; one identity everywhere).

These are transactional messages. Each keeps to one action, states the
expiry, and tells a recipient who did not request it that they can ignore
it. The weekly brief (a commercial message) carries the CASL footer and
unsubscribe link separately; that requirement lives in
`web/lib/brief/render.ts` and does not apply to these.

Supabase sends four template types on our behalf. All four are below so
none stays on the default.

## 1. Confirm signup (the first thing a new member ever sees)

Subject: `Confirm your email to join Signal North`

> You asked to join Signal North Weekly with this address.
>
> Confirm your email and we will take you straight to your account page,
> where you can choose your term and complete checkout.
>
> [Confirm my email]({{ .ConfirmationURL }})
>
> The link expires in one hour. The brief is delivered by email, which is
> why we confirm the address before anything else.
>
> If you did not request this, no account has been created and you can
> ignore this message.

## 2. Magic link (sign-in)

Subject: `Your Signal North sign-in link`

> Here is your sign-in link:
>
> [Sign in to Signal North]({{ .ConfirmationURL }})
>
> It expires in one hour and works once.
>
> If you did not request it, you can ignore this message; your account is
> unchanged and no one can sign in without access to this inbox.

## 3. Reset password

Subject: `Reset your Signal North password`

> Someone asked to reset the password for this address.
>
> [Choose a new password]({{ .ConfirmationURL }})
>
> The link expires in one hour. If this was not you, ignore this message
> and your password stays as it is.

## 4. Change email address

Subject: `Confirm your new email address`

> You asked to move your Signal North account to this address.
>
> [Confirm the change]({{ .ConfirmationURL }})
>
> The brief and every sign-in link will go here from now on. If you did
> not request this, ignore this message and nothing changes.

## Notes for the SMTP cutover (task #57)

- Supabase custom SMTP settings take the host, port, credentials and the
  sender address; the templates above are pasted into Authentication ->
  Email Templates.
- SPF, DKIM and DMARC on the sending domain before the first real send,
  or gov mail filters will eat the very links this exists to deliver.
- The `{{ .ConfirmationURL }}` variable carries our `emailRedirectTo`
  (siteOrigin-derived) only when it is allow-listed; the redirect
  configuration fixed on 2026-08-02 is what keeps these links landing on
  the right host.
