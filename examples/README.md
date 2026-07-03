# LogReducer examples

Runnable examples and copy-paste integration recipes. The [README](../README.md)
is the full API and CLI reference; this directory shows LogReducer in context.

## Run the example script

```bash
uv run python examples/basic_usage.py
```

[basic_usage.py](basic_usage.py) walks through file reduction, metadata output,
logging, all four processing modes, and error handling against a generated
sample log.

## Integration recipes

### Docker container

```dockerfile
FROM python:3.12-slim

RUN pip install logreducer

# Reduce logs during container startup
CMD ["logreducer", "/app/logs/app.log", "-o", "/app/logs/reduced.log", "--stats"]
```

### Kubernetes job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: log-reduction
spec:
  template:
    spec:
      containers:
      - name: logreducer
        image: python:3.12-slim
        command: ["sh", "-c"]
        args:
        - |
          pip install logreducer
          logreducer /logs/app.log -l enhanced -m hybrid -o /output/reduced.log
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
      restartPolicy: Never
```

Memory note: the `standard`/`enhanced`/`maximum` levels cap engine memory at
0.5/1/2 GB respectively (and clamp to 70% of what the container actually has),
so a 1Gi limit comfortably fits the enhanced level.

### CI pipeline (GitHub Actions)

```yaml
- name: Reduce Test Logs
  run: |
    pip install logreducer
    mkdir -p test-summary
    # The CLI reduces one file per run, so loop over the logs.
    for f in test-logs/*.log; do
      logreducer "$f" -l standard -m pattern --format json -o "test-summary/$(basename "$f").json"
    done

- name: Upload Reduced Logs
  uses: actions/upload-artifact@v4
  with:
    name: reduced-logs
    path: test-summary/
```

### Scheduled production reduction

```bash
# Reduce the previous hour's log with maximum quality, JSONL out
logreducer /var/log/app/$(date +%Y%m%d_%H).log \
    -l maximum -m hybrid --format jsonl \
    -o /var/log/reduced/$(date +%Y%m%d_%H).jsonl
```

## More material

- Real-world sample logs to try: [data/samples/](../data/samples/) (public LogHub datasets)
- The test suite doubles as usage documentation: [tests/](../tests/)
- All CLI options: `logreducer --help`
