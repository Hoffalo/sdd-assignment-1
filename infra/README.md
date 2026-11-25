# `infra/`: the one-time Azure setup

After this setup, **only the pipeline changes Azure.** [`.github/workflows/pipeline.yml`](../.github/workflows/pipeline.yml) updates the two Container Apps and uploads the UI on every merge to `main`. Nothing is created or changed by hand in the portal.

## What exists on Azure

Everything is in `rg-lhoffmann`, in `spaincentral` (one of the five regions this Azure for Students subscription allows).

| Resource | Name | Cost model |
|---|---|---|
| Container Apps environment | `lhoffmann-env` | Consumption plan; free when no app runs |
| Container App | `lhoffmann-requests` | Per second while a replica runs; 0 to 1 replica |
| Container App | `lhoffmann-feedback` | Same |
| Log Analytics workspace | created with the environment | Pay per GB; free up to 5 GB a month |
| Azure SQL logical server | `lhoffmann-sql` | Free (no compute of its own) |
| SQL database, serverless | `lhoffmann-requests-db` | Free offer: auto-pauses after 60 min, 32 GB, never billed |
| SQL database, serverless | `lhoffmann-feedback-db` | Same |
| Storage account, static website | `lhoffmannui` | Pay per GB stored and served (cents) |
| User-assigned managed identity | `lhoffmann-github` | Free |

Images are on GHCR (`ghcr.io/hoffalo/avdesk-requests`, `ghcr.io/hoffalo/avdesk-feedback`), which is free for public packages.

## Reproducing the setup

You need the Azure CLI signed in to the subscription (`az login`), Python with `pymssql` (`pip install -r services/requests/requirements.txt`), and OpenSSL. From the repository root:

1. **Create everything.**
   ```bash
   bash infra/setup.sh
   ```
   This registers the resource providers and creates the resources above. It writes the generated passwords to `infra/.secrets.local`, which is gitignored.

2. **Create one login per database.** Allow your own IP on the SQL server for the duration:
   ```bash
   az sql server firewall-rule create -g rg-lhoffmann -s lhoffmann-sql -n setup-my-ip \
     --start-ip-address <your-ip> --end-ip-address <your-ip>
   python infra/create_db_users.py
   az sql server firewall-rule delete -g rg-lhoffmann -s lhoffmann-sql -n setup-my-ip
   ```

3. **Give the pipeline its secrets.** In GitHub, under Settings → Secrets and variables → Actions, add the seven values listed at the bottom of `infra/.secrets.local`. Choose `ADMIN_PASSWORD` yourself.

   | Secret | What it is |
   |---|---|
   | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | Who the pipeline signs in as, through OIDC. These are identifiers, not passwords. |
   | `REQUESTS_DATABASE_URL`, `FEEDBACK_DATABASE_URL` | Each service's own login to its own database |
   | `ADMIN_TOKEN_SECRET` | Signs admin and service tokens; shared by both services |
   | `ADMIN_PASSWORD` | The AV manager's login |

4. **Merge to `main`.** The pipeline pushes the images and points both apps at them. It sets each app's secrets as Container Apps secrets, uploads `ui/` with a generated `config.js`, and waits for `/health`.

5. **Make the two GHCR packages public**, once, after the first push: on each package's settings page, set visibility to Public. Container Apps then pulls without a registry password. The alternative would have been a long-lived token stored in Azure.

6. **Grading access.** Give the professor the Reader role on the resource group:
   ```bash
   az role assignment create --assignee <professor-email> --role Reader \
     --scope $(az group show -n rg-lhoffmann --query id -o tsv)
   ```

## Why the pipeline cannot do more

The managed identity is federated for exactly one subject, `repo:Hoffalo/sdd-assignment-1:ref:refs/heads/main`. A pull request, a fork or another branch cannot get an Azure token at all. Its role is Contributor on `rg-lhoffmann` only, so even a compromised run cannot touch anything else in the subscription. No Azure password exists anywhere.
