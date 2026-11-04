# Deploying on Render (free) + Aiven PostgreSQL (free)

Free-plan facts: the Render web service sleeps after 15 minutes without visitors and takes about a minute to wake;
the Aiven free database powers itself off if unused for a while (power it on from the Aiven console) and has small
storage and limited backups. Fine for a pilot. Move to Render Starter and an Aiven paid plan once customers pay.

## 1. Aiven (done)  2. Aiven user fcm_app (done, keep for later)
For now use the default **avnadmin** Service URI in the app (it must create the tables). Switch to fcm_app when
row-level security is added with the business tables.

## 3. GitHub (Render deploys from a Git repository)
1. Create a free account at github.com. 2. New repository: name `factory-compliance`, **Private**.
3. "uploading an existing file": drag the CONTENTS of the unzipped FCMWeb folder (app, migrations, docs, tests,
   alembic.ini, render.yaml, requirements*.txt, README.md) into the page, then Commit changes.
   (The files must sit at the top level of the repo, not inside an extra FCMWeb folder.)

## 4. Render web service
New + > Web Service > connect GitHub > select the repo.
Name factory-compliance | Region Singapore | Branch main | Runtime Python 3 | Instance type **Free**
Build command: `pip install -r requirements.txt && alembic upgrade head`
Start command: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:$PORT --forwarded-allow-ips="*" --timeout 120`
Health check path: `/healthz`
Environment variables: PYTHON_VERSION=3.12.3, APP_ENV=production, SECRET_KEY=<long random text>,
DATABASE_URL=<Aiven avnadmin Service URI>, AIVEN_CA_CERT=<Aiven CA certificate text>,
SUPERADMIN_USERNAME=<your login>, SUPERADMIN_PASSWORD=<10+ chars, letters and digits>.

## 5. First start
Create Web Service > wait for "Live". Logs should show `bootstrap: Super Admin created`. Open the onrender.com URL,
sign in, set a new password, then **delete SUPERADMIN_PASSWORD** from Render > Environment.
Create Organisation > Company > Users.

## Local development
pip install -r requirements-dev.txt; set APP_ENV=development; uvicorn app.main:app --reload; python -m pytest tests -q
