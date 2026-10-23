# Mkondo Home Technology — starter project

## Important business rule
This starter records referrals, submitted product sales, and admin-reviewed transactions. It does **not** pay commissions just because someone recruits a member or pays a membership fee. Configure commissions only against verified genuine product sales, with transparent terms and appropriate local legal/accounting review.

## Project structure
- `linkora.py` — Streamlit application
- `style.css` — colors and interface styling
- `requirements.txt` — Python dependencies
- `images/mkondo.png` — optional logo/image (add your own file)
- `.streamlit/secrets.toml.example` — example settings only

## Run locally (Windows PowerShell)
1. Install Python 3.11 or newer.
2. Open PowerShell in this folder.
3. Create a virtual environment:
   `py -m venv .venv`
4. Activate it:
   `.\.venv\Scripts\Activate.ps1`
5. Install dependencies:
   `python -m pip install -r requirements.txt`
6. For a quick local test, leave `DATABASE_URL` unset; the app uses `mkondo_dev.db` SQLite.
7. Run:
   `streamlit run linkora.py`

## Admin account
The app reads `ADMIN_USERNAME` and `ADMIN_PASSWORD` from environment variables. Set a strong password before starting the app. The username defaults to `GEORGE2002`, but no admin password is hard-coded in the source. On first run, the app creates the admin account if `ADMIN_PASSWORD` is set.

PowerShell example (for the current terminal only):
`$env:ADMIN_USERNAME="GEORGE2002"`
`$env:ADMIN_PASSWORD="use-a-long-unique-password-here"`
`streamlit run linkora.py`

## PostgreSQL
Set `DATABASE_URL` to your PostgreSQL connection string. For local development, SQLite is used by default. On Render, add the internal PostgreSQL connection URL as an environment variable when the web service and database are in the same Render region.

Example:
`postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`

Never commit real passwords or database credentials to a public repository.

## Before production
This is a starter, not a fully audited financial platform. Before accepting real payments:
- use a proper password-reset and email/phone verification process;
- add CSRF/session and rate-limiting protections appropriate to the deployment;
- validate sales with an order/payment provider, not only a typed reference;
- implement idempotent ledger entries and reconciliation;
- add audit logs and stronger admin access controls;
- back up PostgreSQL and test restoration;
- have commission terms and the business model reviewed locally.
