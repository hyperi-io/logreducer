# LogReducer Development TODO

## High Priority Features

### Prometheus Metrics Integration
**Epic**: Replace current telemetry system with proper Prometheus metric telemetry

**Context**: Current telemetry system uses JSON events and HTTP push, which doesn't fit Prometheus pull-based architecture. Need enterprise-grade metrics for monitoring.

**Tasks**:
- [ ] Add `prometheus-client` dependency to pyproject.toml
- [ ] Create metrics endpoint at `/metrics` for Prometheus scraping
- [ ] Implement core metrics:
  - `logreducer_processing_total` (Counter) - Total processing jobs by mode/level
  - `logreducer_processing_duration_seconds` (Histogram) - Processing time distribution
  - `logreducer_bytes_processed_total` (Counter) - Total bytes processed
  - `logreducer_reduction_ratio` (Histogram) - Reduction percentage achieved
  - `logreducer_memory_usage_bytes` (Gauge) - Memory usage during processing
  - `logreducer_errors_total` (Counter) - Total errors by type
- [ ] Support both pull (metrics endpoint) and push (Prometheus Pushgateway) patterns
- [ ] Add metrics configuration to BigDialConfig
- [ ] Update CLI to expose metrics endpoint option
- [ ] Replace existing JSON-based telemetry system with Prometheus metric telemetry
- [ ] Add Prometheus integration documentation

**Priority**: High - Required for production monitoring

### LLM Integration
**Epic**: Optional Large Language Model integration for advanced log analysis