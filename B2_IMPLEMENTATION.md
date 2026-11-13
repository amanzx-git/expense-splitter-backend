# B2 Accounts and Authentication

B2 implements session-based accounts only. B3-B9 remain outside this change.
The authoritative sources are the sibling Guide directory's Shared Contract R1.2
and Backend Complete Guide R1.2 (later R1.2 rules supersede older examples).

All paths below have prefix `/api/v1/`:

| Method | Path | Success |
| --- | --- | --- |
| GET | auth/csrf/ | 200 message, CSRF cookie |
| POST | auth/register/ | 201 user + message |
| POST | auth/verify-email/ | 200 message |
| POST | auth/resend-verification/ | 200 generic message |
| POST | auth/login/ | 200 user, session cookie |
| POST | auth/logout/ | 204 |
| POST | auth/password-reset/ | 200 generic message |
| POST | auth/password-reset/confirm/ | 200 message |
| GET, PATCH | users/me/ | 200 user |
| POST | users/me/photo/ | 200 profile_photo_url |
| GET | users/search/?username=pe | 200 results |

Verification and reset links expire after 24 hours. Verification uses its own
expiry setting and cryptographic purpose; successful verification invalidates all
outstanding verification links. Password changes invalidate reset tokens and
existing sessions through Django's session authentication hash. Verification and
reset confirmation lock the user row to serialize simultaneous redemption.
Neither registration, verification nor password reset signs the user in.

CSRF is required for every unsafe request, including anonymous auth requests.
Login rotates the session key and CSRF cookie. Logout flushes the session.
Passwords use Django's validators and hashing. Profile edits reject unknown and
protected fields. Search is a normalized prefix lookup, ordered by username/UUID,
with at most 10 active verified accounts and only public identity fields.
Photo uploads validate bytes with Pillow, fully decode the image, enforce 2 MiB,
use generated filenames and delete the previous file after a successful commit.
Local media is served only when DEBUG=True. Admin edits remain superuser-only.

Rate limits: register 10/hour; login 10/minute; verification and reset confirmation
20/hour each; resend and reset request 5/hour each; search 30/minute.
Anonymous limits use REMOTE_ADDR (forwarded headers are not trusted); authenticated
search uses user UUID. DRF local-memory throttles are per process, reset on restart,
and have approximate concurrency behavior. They are basic abuse protection, not a
shared multiworker brute-force lockout. Email delivery is synchronous; acknowledgments
are identical for eligible and unknown emails, but delivery timing is not equalized.
No new dependency, migration, JWT, infrastructure or frontend change was needed.

The contract does not prescribe exact generic acknowledgment wording, a reset-token
error code or the reset TTL. This implementation uses generic messages,
`400 INVALID_RESET_TOKEN`, and a 24-hour reset TTL. Invalid credentials use
`401 AUTHENTICATION_REQUIRED` with `Invalid email or password.` The explicitly
specified unverified-login response and verification error code are preserved.

Run checks using the existing virtual environment and configured PostgreSQL:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test accounts common --verbosity=2 --noinput
.\.venv\Scripts\python.exe manage.py test --verbosity=1 --noinput
.\.venv\Scripts\python.exe manage.py runserver localhost:8000
```

Manual browser/API walkthrough (local HTTP requires DJANGO_DEBUG=True):

1. Open http://localhost:8000/api/v1/auth/csrf/ in a browser and open DevTools.
2. Run the following in that browser's console. It rereads the CSRF cookie on every
   call, including after login rotation. Use a fresh email/username when repeating.

```javascript
async function api(path, method = 'GET', data) {
  const csrf = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1];
  const response = await fetch('/api/v1/' + path, {
    method, credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
    ...(data === undefined ? {} : { body: JSON.stringify(data) })
  });
  return { status: response.status, body: response.status === 204 ? null : await response.json() };
}
await api('auth/register/', 'POST', {
  username: 'manual_user', full_name: 'Manual User', email: 'manual@example.com',
  password: 'UnusualStrongPass491!', confirm_password: 'UnusualStrongPass491!'
});
// Copy uid/token from the verification URL printed by Django's console email backend.
await api('auth/verify-email/', 'POST', { uid: 'COPY_UID', token: 'COPY_TOKEN' });
await api('auth/login/', 'POST', { email: 'manual@example.com', password: 'UnusualStrongPass491!' });
await api('users/me/');
await api('users/me/', 'PATCH', { full_name: 'Updated User', upi_id: 'manual@upi' });
await api('users/search/?username=ma');
await api('auth/password-reset/', 'POST', { email: 'manual@example.com' });
// Copy uid/token from the reset URL printed in the terminal.
await api('auth/password-reset/confirm/', 'POST', {
  uid: 'COPY_UID', token: 'COPY_TOKEN',
  new_password: 'ReplacementStrongPass817!', confirm_password: 'ReplacementStrongPass817!'
});
await api('users/me/'); // 401: previous session invalidated
await api('auth/login/', 'POST', { email: 'manual@example.com', password: 'ReplacementStrongPass817!' });
await api('auth/logout/', 'POST', {}); // 204
```

For photo testing, after login add an `<input type="file" id="photo">` through
DevTools, select a JPG/PNG/WebP, then run:

```javascript
const form = new FormData();
form.append('photo', document.querySelector('#photo').files[0]);
const csrf = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1];
await fetch('/api/v1/users/me/photo/', {
  method: 'POST', credentials: 'include', headers: { 'X-CSRFToken': csrf }, body: form
}).then(r => r.json());
```

Check that the returned absolute image URL renders. Repeat an unsafe request without
X-CSRFToken to confirm 403 CSRF_FAILED. For frontend integration use localhost:5173
consistently, relative API URLs, credentials included and Vite's `/api` proxy to
localhost:8000 with changeOrigin:false. The separate React/Vite browser integration
must be checked when that frontend is running; the backend test suite exercises
real session cookies and enforced CSRF but does not substitute for that check.

Validation performed against the configured PostgreSQL database:

- `manage.py check`: passed, no issues.
- `manage.py makemigrations --check --dry-run`: passed, no changes detected.
- `manage.py showmigrations accounts`: both existing migrations applied.
- `manage.py test accounts common --verbosity=1 --noinput`: 62 passed, 0 failed, 0 skipped.
- `manage.py test --verbosity=1 --noinput`: 62 passed, 0 failed, 0 skipped.
- `git diff --check`: passed (Git may report Windows line-ending notices).

The first expanded test run found one fixture failure (a valid image named .svg);
the fixture was corrected to an accepted image extension and subsequent runs passed.
Manual browser/Vite checks above are provided for execution and were not performed
as part of this backend verification. No commit, push or deployment was performed.
Next implementation milestone is B3 Groups.
