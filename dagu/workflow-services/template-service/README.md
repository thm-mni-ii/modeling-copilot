# template-service

Template for future short-lived Dagu workflow-service containers. It contains
no evaluation business logic; capability images set `WORKFLOW_CAPABILITY` and
receive deterministic dummy data so the workflow can be played through:

- input as JSON (via `TEMPLATE_INPUT` env var, or stdin if unset)
- output as JSON on stdout
- logs on stderr
- exit code `0` on success, non-zero on failure

`TEMPLATE_INPUT` may include `step`, `input`, and `demoDelaySeconds`. Output
always contains `status`, `summary`, and `result`; it stays compatible with the
original `echo` field used by the template test.

## Build

```bash
docker build -t template-service:0.1.0 .
```

## Run

```bash
docker run --rm -e TEMPLATE_INPUT='{"message":"hi"}' template-service:0.1.0
```

## Test

```bash
python -m pytest tests/
```
