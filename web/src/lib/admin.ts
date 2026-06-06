// Operators with admin-console access. Kept in sync with the API's ADMIN_EMAILS
// (app/config.py). Used only to show/hide the Admin nav link; the API is the
// real gate (returns 403 for non-admins regardless of the UI).
export const ADMIN_EMAILS = [
  "lydiasolomon137@gmail.com",
  "thedevassist@gmail.com",
];

export function isAdminEmail(email?: string | null): boolean {
  return !!email && ADMIN_EMAILS.includes(email.toLowerCase());
}
