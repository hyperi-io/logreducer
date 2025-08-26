# LogReducer Project Structure

## Directory Layout

```
logreducer/
├── .github/              # GitHub Actions CI/CD workflows
│   └── workflows/
│       ├── ci.yml        # Main CI pipeline
│       └── release.yml   # Semantic release workflow
│
├── data/                # Data and sample datasets
│   └── samples/
│       └── samples/
│           ├── apache_access.log      # Apache web server logs
│           ├── bgl_supercomputer.log  # BlueGene/L supercomputer logs
│           ├── hdfs_system.log        # Hadoop distributed filesystem logs
│           ├── healthapp_android.log  # Android health app logs
│           ├── linux_system.log       # Linux system logs
│           ├── openstack_nova.log     # OpenStack cloud platform logs
│           ├── proxifier_network.log  # Network proxy logs
│           ├── spark_application.log  # Apache Spark logs
│           ├── thunderbird_hpc.log    # HPC cluster logs
│           └── zookeeper_cluster.log  # ZooKeeper coordination logs
│
├── docs/                # Project documentation
│   ├── DEPLOYMENT.md    # Deployment guide
│   └── PROJECT_STRUCTURE.md  # This file
│
├── logs/                # Application logs (git-ignored)
│
├── output/              # Processed log outputs (git-ignored)
│   ├── *.log           # Reduced log files
│   └── *.meta.json     # Metadata for processed logs
│
├── scripts/             # Utility scripts
│   ├── build.py         # Package building script
│   ├── release.sh       # Local release automation
│   ├── setup_lfs.sh     # Git LFS setup script
│   ├── test.sh          # Local testing script
│   └── version.py       # Version management script
│
├── src/                 # Source code
│   └── logreducer/      # Main package
│       ├── __init__.py      # Package initialization
│       ├── anomaly.py       # Anomaly detection module
│       ├── cli.py           # Command-line interface
│       ├── config.py        # Configuration management
│       ├── core.py          # Core processing engine
│       ├── memory.py        # Memory management utilities
│       ├── patterns.py      # Pattern extraction
│       ├── py.typed         # PEP 561 type hint marker
│       └── temporal.py      # Temporal analysis
│
├── tests/               # Test suite
│   ├── __init__.py
│   ├── conftest.py      # Pytest fixtures and configuration
│   ├── integration/     # Integration tests
│   │   └── test_end_to_end.py
│   └── unit/           # Unit tests
│       ├── test_anomaly.py
│       ├── test_cli.py
│       ├── test_config.py
│       ├── test_core.py
│       ├── test_memory.py
│       ├── test_patterns.py
│       └── test_temporal.py
│
├── .env                 # Local environment configuration (git-ignored)
├── .env.example         # Environment configuration template
├── .gitattributes       # Git attributes and LFS configuration
├── .gitignore           # Git ignore patterns
├── .releaserc.json      # Semantic release configuration
├── CHANGELOG.md         # Version history and release notes
├── LICENSE             # MIT license
├── package.json         # Node.js dependencies for semantic release
├── pyproject.toml       # Python package configuration
├── README.md           # Project documentation
└── VERSION             # Current version number
```

## Key Files

### Configuration Files

- **pyproject.toml**: Modern Python packaging configuration with all dependencies and build settings
- **.env.example**: Template for environment variables controlling deployments and CI/CD
- **.releaserc.json**: Semantic release automation configuration
- **package.json**: Node.js dependencies for semantic release tooling

### Documentation

- **README.md**: Main project documentation with usage examples
- **CHANGELOG.md**: Comprehensive version history (v1.0.0 to v3.1.14)
- **docs/DEPLOYMENT.md**: Detailed deployment instructions for JFrog Artifactory

### Source Code

The `logreducer/` package contains:
- **Core modules**: Pattern extraction, anomaly detection, temporal analysis
- **Infrastructure**: Memory management, configuration, CLI
- **Processing**: Stream processing with memory safety for large files

### Testing

- **Unit tests**: Comprehensive coverage (92%) of all modules
- **Integration tests**: End-to-end testing with real sample datasets
- **Fixtures**: Pytest fixtures for consistent test data

### Samples

Real-world log datasets from LogHub academic repository:
- 10 different log formats from various systems
- Used for integration testing and benchmarking
- Tracked with Git LFS for efficient storage

## Development Workflow

1. **Environment Setup**
   ```bash
   cp .env.example .env
   # Edit .env to configure deployment targets
   ```

2. **Install Dependencies**
   ```bash
   pip install -e ".[dev,enhanced]"
   npm ci  # For semantic release
   ```

3. **Run Tests**
   ```bash
   pytest tests/
   pytest --cov=logreducer --cov-report=term-missing
   ```

4. **Release Process**
   ```bash
   ./scripts/release.sh
   # Or use GitHub Actions for automated releases
   ```

## CI/CD Pipeline

- **GitHub Actions**: Automated testing, building, and deployment
- **Semantic Release**: Automated versioning based on commit messages
- **Deployment Targets**: 
  - JFrog Artifactory (private PyPI)
  - PyPI (public, disabled by default)
  - GitHub Releases (disabled by default)

## Git LFS

Large files are tracked with Git LFS:
- All `*.log` files
- Sample datasets
- Model files and weights
- Large documentation assets

Run `./scripts/setup-lfs.sh` to initialize Git LFS in your repository.