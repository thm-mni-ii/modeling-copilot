# Releases and container images

Docker images are published only when a Git tag in the `vX.Y.Z` format is pushed.
The workflow verifies that the tagged commit is part of `main`, then publishes
`ghcr.io/OWNER/REPOSITORY-api` and `ghcr.io/OWNER/REPOSITORY-web` with the
release version and `latest` tags.

## Configure GitHub branches

For `dev`:

- Set it as the repository's default branch.
- Use pull requests for changes and require the CI checks when they are available.

For `main`:

- Enable branch protection.
- Allow merges only through pull requests and require CI status checks.
- Disable force pushes and branch deletion.
- For `dev` to `main`, prefer a normal merge commit. Do not repeatedly squash
  merge the two long-lived branches.

## GitHub Packages / GHCR

No package or secret needs to be created for the build. The workflow uses the
repository-provided `GITHUB_TOKEN`. After the first successful release, find
the two containers at **Repository / Profile / Organization -> Packages**:

- `REPOSITORY-api`
- `REPOSITORY-web`

Set each package's desired visibility (`private` or `public`) there.

## Create a release

### Database migration for submissions

Migration `09_submissions_feedback` follows `08_public_case_studies`. It creates
the nine submission/feedback collections and their indexes, and initializes the
global feedback configuration only if it does not exist. Existing models,
language configurations, submissions and feedback remain unchanged.

The API image applies registered migrations before starting the server. To
preview this step separately using the updated image:

```bash
docker compose run --rm api python -m modeling_api.db.migrations --migration 09_submissions_feedback
```

To apply the previewed step explicitly, append `--apply`. Its prerequisites must
already be completed. Successful execution is recorded in `schema_migrations`;
repeated runs skip the completed step. Use the existing backup procedure before
updating the deployment.

### Portainer instance configuration

1. Create namespace `modeling-copilot` and manage its instance ConfigMaps and
   Secrets separately in Portainer. Required entries and suggested values are
   listed at the top of [`k3s-portainer.yaml`](../k3s-portainer.yaml).
2. Supply credentials and an EC P-256 PEM key pair for `ES256`.
3. Deploy `k3s-portainer.yaml`; restart API and Collab-Kit after config changes.

Keep the namespace and instance configuration on redeploy. When switching from
the old manifest, back up ConfigMaps first; Portainer may remove omitted resources.

### Tag and publish

After the `dev` to `main` pull request has been merged, create and push the
annotated release tag locally:

```bash
git switch main
git pull origin main
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

Pushing the tag starts the GHCR workflow. Creating a GitHub Release does not
start the build. Optionally create one afterwards in the browser:

**GitHub Repository -> Releases -> Draft a new release -> choose existing tag
`v0.1.0` -> generate release notes -> Publish release**.

## Verify the result

After a successful workflow, these image tags exist (replace `OWNER` and
`REPOSITORY`):

```text
ghcr.io/OWNER/REPOSITORY-api:v0.1.0
ghcr.io/OWNER/REPOSITORY-api:latest
ghcr.io/OWNER/REPOSITORY-web:v0.1.0
ghcr.io/OWNER/REPOSITORY-web:latest
```

Optionally test them locally:

```bash
docker pull ghcr.io/OWNER/REPOSITORY-api:v0.1.0
docker pull ghcr.io/OWNER/REPOSITORY-web:v0.1.0
```
