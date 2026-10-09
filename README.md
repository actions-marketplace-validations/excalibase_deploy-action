# Deploy to Excalibase

A GitHub Action that deploys a pushed image to an [Excalibase](https://excalibase.io) app and waits until it is live. The step fails when the deploy does.

```yaml
      - uses: excalibase/deploy-action@v1
        with:
          app: proj-abc123/web          # <project id>/<app id>
          image: ghcr.io/acme/web@${{ steps.build.outputs.digest }}
          token: ${{ secrets.EXCALIBASE_TOKEN }}
```

Studio's pipeline page (Containers, your app, Pipeline) writes the whole workflow for you: build and push with the Docker actions, then this step.

## Inputs

| Input | Required | Default | |
|---|---|---|---|
| `app` | yes | | `<project id>/<app id>`, or the app id alone with `project` |
| `project` | no | | the project id, when `app` is the app id alone |
| `image` | yes | | the image to deploy; pass the pushed digest so the deploy runs exactly what was built |
| `token` | yes | | a personal access token bound to the project with the write scope, kept as a secret |
| `api-url` | no | `https://app.excalibase.io/api` | your Excalibase API, when self-hosted |
| `commit-sha` | no | `${{ github.sha }}` | the commit shown beside the deploy in Studio |
| `timeout` | no | `900` | seconds to wait for the deploy to be live |

## Outputs

`deploy-id`, `status` (`succeeded`) and `url`, where the app is served.

## How it waits

It asks the deploy API to answer once the deploy has finished (`POST .../deploy?wait=true`). An API that does not wait answers at once, and the action then polls the deploy until it is live, failed, or replaced by a newer deploy. Either way the step ends only when the deploy does, or after `timeout`.

Any other CI can do the same with one command, on an Excalibase API that waits (an older one answers 202 at once with the started deploy, which the action follows and a bare `curl` does not):

```sh
curl --fail-with-body -sS -X POST "https://app.excalibase.io/api/projects/$PROJECT/apps/$APP/deploy?wait=true" \
  -H "Authorization: Bearer $EXCALIBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"image\":\"$IMAGE\",\"commitSha\":\"$COMMIT_SHA\"}"
```

## License

Apache 2.0
