// Member-welcome email (template 03), the post-payment welcome the webhook
// sends when checkout-first provisioning succeeds (operator 2026-08-03).
//
// SOURCE OF TRUTH IS web/emails/03-member-welcome.{html,txt}. The raw template
// bytes are embedded here verbatim so the send path needs no runtime file read
// (which Next output-tracing would have to be told to bundle, a silent-failure
// risk for a paying member). welcome-email.test.ts asserts these constants stay
// byte-identical to the reviewed files, so the thing shipped is the thing the
// operator approved: divergence fails CI rather than reaching an inbox.
//
// TRANSACTIONAL: a service message about the member own account. It carries NO
// CASL unsubscribe link, by the operator ruling that only the free-list welcome
// does. Do not add one.
//
// The two placeholders are substituted at send time:
//   {{signin_url}}        the one-time sign-in link (token_hash magiclink)
//   {{first_brief_date}}  the Monday the first member-edition brief lands

export const MEMBER_WELCOME_SUBJECT =
  "Your Signal North membership is active";

export const MEMBER_WELCOME_HTML_TEMPLATE = "<!DOCTYPE html>\n<html lang=\"en\" xmlns:v=\"urn:schemas-microsoft-com:vml\" xmlns:o=\"urn:schemas-microsoft-com:office:office\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n<meta http-equiv=\"X-UA-Compatible\" content=\"IE=edge\">\n<meta name=\"color-scheme\" content=\"light dark\">\n<meta name=\"supported-color-schemes\" content=\"light dark\">\n<title>Your Signal North membership is active</title>\n<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->\n<style>\n  body{margin:0;padding:0;width:100%!important;-webkit-text-size-adjust:100%;}\n  img{border:0;line-height:100%;outline:none;text-decoration:none;}\n  table{border-collapse:collapse;}\n  a{color:#C8102E;}\n  @media screen and (max-width:600px){\n    .col{width:100%!important;}\n    .pad{padding-left:24px!important;padding-right:24px!important;}\n    .h1{font-size:26px!important;line-height:32px!important;}\n  }\n  :root{color-scheme:light dark;supported-color-schemes:light dark;}\n</style>\n</head>\n<body style=\"margin:0;padding:0;background-color:#F5F3EF;\">\n<div style=\"display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;\">Your annual membership is on record. Sign in to open the full procurement record.</div>\n<div style=\"display:none;white-space:nowrap;font-size:15px;line-height:0;\">&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" bgcolor=\"#F5F3EF\" style=\"width:100%;background-color:#F5F3EF;\">\n<tr><td align=\"center\" style=\"padding:32px 12px;\">\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"560\" class=\"col\" style=\"width:560px;max-width:560px;background-color:#F5F3EF;border-top:3px solid #0D1520;\">\n<tr><td style=\"padding:36px 40px 0 40px;\">\n<div style=\"font-family:Georgia,'Iowan Old Style','Palatino Linotype',Palatino,'Times New Roman',serif;font-size:21px;line-height:24px;mso-line-height-rule:exactly;letter-spacing:0.16em;text-transform:uppercase;color:#0D1520;\">Signal North</div>\n<div style=\"font-family:'Courier New',Consolas,'Lucida Console',monospace;font-size:10px;line-height:16px;mso-line-height-rule:exactly;letter-spacing:0.2em;text-transform:uppercase;color:#6B7280;padding-top:8px;\">Canadian public safety procurement intelligence</div>\n</td></tr>\n<tr><td style=\"padding:24px 40px 0px 40px;\"><table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"width:100%;\"><tr><td height=\"1\" style=\"height:1px;line-height:1px;font-size:0;background-color:#D9D3C8;\">&nbsp;</td></tr></table></td></tr>\n<tr><td class=\"pad\" style=\"padding:32px 40px 0px 40px;\"><div style=\"font-family:'Helvetica Neue',Helvetica,Arial,'Segoe UI',Tahoma,sans-serif;font-size:11px;line-height:16px;mso-line-height-rule:exactly;letter-spacing:0.18em;text-transform:uppercase;color:#C8102E;font-weight:bold;\">Membership active</div><div style=\"font-family:Georgia,'Iowan Old Style','Palatino Linotype',Palatino,'Times New Roman',serif;font-size:31px;line-height:38px;mso-line-height-rule:exactly;color:#0D1520;margin:14px 0 0 0;letter-spacing:-0.01em;\">The record is open to you</div><p style=\"margin:18px 0 0 0;font-family:'Helvetica Neue',Helvetica,Arial,'Segoe UI',Tahoma,sans-serif;font-size:16px;line-height:26px;mso-line-height-rule:exactly;color:#232B37;\">Your annual membership is on record. From Monday {{first_brief_date}} you will receive the member edition of the intelligence brief, which carries the full tender and award tables rather than the summary, and the sources for every line in it.</p><table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" style=\"margin:30px 0 4px 0;\"><tr><td align=\"center\" bgcolor=\"#C8102E\" style=\"background-color:#C8102E;padding:15px 30px;\"><a href=\"{{signin_url}}\" style=\"font-family:'Helvetica Neue',Helvetica,Arial,'Segoe UI',Tahoma,sans-serif;font-size:12px;line-height:14px;mso-line-height-rule:exactly;font-weight:bold;letter-spacing:0.14em;text-transform:uppercase;color:#FFFFFF;text-decoration:none;display:block;\">Sign in</a></td></tr></table><div style=\"margin:22px 0 0 0;font-family:'Courier New',Consolas,'Lucida Console',monospace;font-size:11px;line-height:19px;color:#6B7280;word-break:break-all;\">Or paste this address into your browser:<br><span style=\"color:#232B37;\">{{signin_url}}</span></div></td></tr><tr><td style=\"padding:34px 40px 0px 40px;\"><table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"width:100%;\"><tr><td height=\"1\" style=\"height:1px;line-height:1px;font-size:0;background-color:#D9D3C8;\">&nbsp;</td></tr></table></td></tr><tr><td class=\"pad\" style=\"padding:26px 40px 0px 40px;\"><p style=\"margin:18px 0 0 0;font-family:'Helvetica Neue',Helvetica,Arial,'Segoe UI',Tahoma,sans-serif;font-size:16px;line-height:26px;mso-line-height-rule:exactly;color:#232B37;\">Two things worth knowing. The record is searchable back to January 2019, and saved searches send you a note the day a matching document appears. And the brief is written by people, so if something in it is wrong or incomplete, replying to it reaches the desk that wrote it.</p><p style=\"margin:18px 0 0 0;font-family:'Helvetica Neue',Helvetica,Arial,'Segoe UI',Tahoma,sans-serif;font-size:14px;line-height:26px;mso-line-height-rule:exactly;color:#232B37;\">If you did not authorize this payment, reply to this message and we will reverse it the same day.</p></td></tr><tr><td style=\"padding:32px 40px 0px 40px;\"><table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"width:100%;\"><tr><td height=\"1\" style=\"height:1px;line-height:1px;font-size:0;background-color:#D9D3C8;\">&nbsp;</td></tr></table></td></tr>\n<tr><td style=\"padding:0 40px 44px 40px;\">\n<div style=\"font-family:'Courier New',Consolas,'Lucida Console',monospace;font-size:10px;line-height:18px;mso-line-height-rule:exactly;letter-spacing:0.04em;color:#6B7280;\">This is a service message about your Signal North account. It is not a marketing message and carries no unsubscribe link.</div>\n\n</td></tr>\n</table>\n</td></tr>\n</table>\n</body>\n</html>";

export const MEMBER_WELCOME_TEXT_TEMPLATE = "SIGNAL NORTH\nCanadian public safety procurement intelligence\n------------------------------------------------------------\n\nMEMBERSHIP ACTIVE\n\nTHE RECORD IS OPEN TO YOU\n\nYour annual membership is on record. From Monday {{first_brief_date}} you will receive the\nmember edition of the intelligence brief, which carries the full tender and award\ntables rather than the summary, and the sources for every line in it.\n\nSign in:\n{{signin_url}}\n\n------------------------------------------------------------\n\n\n------------------------------------------------------------\n\nTwo things worth knowing. The record is searchable back to January 2019,\nand saved searches send you a note the day a matching document appears.\nAnd the brief is written by people, so if something in it is wrong or\nincomplete, replying to it reaches the desk that wrote it.\n\nIf you did not authorize this payment, reply to this message and we will\nreverse it the same day.\n\n------------------------------------------------------------\nSIGNAL NORTH\nCanadian public safety procurement intelligence\n\nThis is a service message about your Signal North account. It is not a\nmarketing message and carries no unsubscribe link.\n";

export interface MemberWelcomeInput {
  signInLink: string;
  firstBriefDate: string;
}

function fill(template: string, input: MemberWelcomeInput): string {
  // Global replace: {{signin_url}} appears twice in the HTML (button + the
  // paste-this-address fallback), so a one-shot replace would leave the second
  // occurrence as a literal placeholder in a real member email.
  return template
    .split("{{signin_url}}").join(input.signInLink)
    .split("{{first_brief_date}}").join(input.firstBriefDate);
}

export interface RenderedEmail {
  subject: string;
  html: string;
  text: string;
}

export function renderMemberWelcome(input: MemberWelcomeInput): RenderedEmail {
  return {
    subject: MEMBER_WELCOME_SUBJECT,
    html: fill(MEMBER_WELCOME_HTML_TEMPLATE, input),
    text: fill(MEMBER_WELCOME_TEXT_TEMPLATE, input),
  };
}
