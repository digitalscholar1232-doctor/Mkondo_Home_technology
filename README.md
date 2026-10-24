# Mkondo Home Technology project

#Important business rule
This starter records referrals, submitted product sales, and admin-reviewed transactions. It does pay commissions just because someone recruits a member or pays a membership fee. Configure commissions only against verified genuine product sales, with transparent terms and appropriate local legal/accounting review.

## Project structure
- `linkora.py` — Streamlit application
- `style.css` — colors and interface styling
- `requirements.txt` — Python dependencies
- `images/mkondo.png` — optional logo/image (add your own file)
- `.streamlit/secrets.toml.example` — example settings only

## Run locally (Windows PowerShell)
1. Install Python 3.11 or newer.
2. Open PowerShell in this folder.

## Admin account
The app reads `ADMIN_USERNAME` and `ADMIN_PASSWORD` from environment variables. Set a strong password before starting the app. The username defaults to `GE`, but no admin password is hard-coded in the source. On first run, the app creates the admin account if `ADMIN_PASSWORD` is set.

PowerShell example (for the current terminal only):
`$env:ADMIN_USERNAME="GEORGE2002"`
`$env:ADMIN_PASSWORD="use-a-long-unique-password-here"`
`streamlit run linkora.py`

## PostgreSQL
Set `DATABASE_URL` to your PostgreSQL connection string. For local development, SQLite is used by default. On Render, add the internal PostgreSQL connection URL as an environment variable when the web service and database are in the same Render region.

Example:
`postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`

Never commit real passwords or database credentials to a public repository
