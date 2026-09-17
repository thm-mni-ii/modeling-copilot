# template-service

Template for future short-lived Dagu workflow-service containers. Contains no
business logic - it only demonstrates the expected container contract:

- input as JSON (via `TEMPLATE_INPUT` env var, or stdin if unset)
- output as JSON on stdout
- logs on stderr
- exit code `0` on success, non-zero on failure

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
