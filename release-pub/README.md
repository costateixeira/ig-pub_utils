# FHIR IG Publisher

A Python tool for building and publishing FHIR Implementation Guides. Runs via command line, GUI, or GitHub Actions.

## Features

- Build and publish FHIR IGs using the official HL7 FHIR IG Publisher
- Publish to web roots and GitHub Pages
- Sparse checkout for large repositories  
- Automatic pull request creation
- GUI interface for local development
- GitHub Actions workflow for CI/CD
- Configuration merging (global + local settings)

## Quick Start

The tool can run in three ways:

### 1. GitHub Actions (CI/CD)

Add this workflow to your FHIR IG repository:

```yaml
# .github/workflows/publish.yml
name: Publish IG

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  publish:
    uses: costateixeira/smart-html/.github/workflows/release.yml@main
    with:
      pubreq_package_id: "your.org.ig.id"
      pubreq_version: "1.0.0" 
      pubreq_canonical: "https://your-org.org/fhir/ig"
      pubreq_path: "https://your-org.org/fhir/ig/1.0.0"
      sitepreview_dir: "sitepreview"
    permissions:
      contents: write
```

### 2. GUI (Local Development)

```bash
pip install -r requirements-gui.txt
python ig_publisher.py --gui
```

### 3. Command Line

```bash
pip install -r requirements.txt
python ig_publisher.py \
  --source ./my-ig \
  --enable-sparse \
  --publish-gh-pages
```

## Installation

### Prerequisites

- **Python 3.11+** with pip
- **Java 17+** (for FHIR IG Publisher)
- **Node.js 18+** with npm (for SUSHI)
- **Ruby 3.0+** with gems (for Jekyll)
- **Git** (for repository operations)

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3-tk \
  graphviz \
  ruby-full \
  build-essential \
  zlib1g-dev \
  rsync
```

**macOS:**
```bash
brew install graphviz ruby
gem install jekyll bundler
```

**Windows:**
```bash
# Install via chocolatey
choco install graphviz ruby
gem install jekyll bundler
```

### Python Dependencies

```bash
# Basic requirements
pip install -r requirements.txt

# For GUI support
pip install -r requirements-gui.txt
```

## Configuration

### Global Configuration (`release-config.yaml`)

Create a `release-config.yaml` file in your repository root:

```yaml
# Repository settings
source_repo: https://github.com/your-org/your-ig
source_branch: main
webroot_repo: https://github.com/your-org/smart-html
webroot_branch: main
history_repo: https://github.com/HL7/fhir-ig-history-template
history_branch: master

# Performance optimization
enable_sparse_checkout: true
sparse_dirs:
  - templates
  - assets
  - css
  - js

# GitHub integration
enable_pr_creation: true
webroot_pr_target_branch: main
registry_pr_target_branch: master

# Authentication (optional - auto-detected in GitHub Actions)
github_token: ""  # Use environment variable instead
```

### Environment-Specific Configuration

The tool supports hierarchical configuration:

1. **Global defaults** (from smart-html repository)
2. **Local overrides** (your `release-config.yaml`)
3. **Environment variables**
4. **Command line arguments**

### Environment Variables

```bash
# GitHub Actions (automatically set)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export GITHUB_REPOSITORY="your-org/your-ig"
export GITHUB_ACTIONS="true"

# Manual/Local runs
export GH_PAT="ghp_xxxxxxxxxxxx"
export GLOBAL_RELEASE_CONFIG="/path/to/global-config.yaml"

# Publication request overrides
export PUBREQ_PACKAGE_ID="your.org.ig.id"
export PUBREQ_VERSION="1.0.0"
export PUBREQ_CANONICAL="https://your-org.org/fhir/ig"
export PUBREQ_PATH="https://your-org.org/fhir/ig/1.0.0"
```

## Usage Examples

### Local Development with GUI

```bash
# Launch GUI interface
python ig_publisher.py --gui
```

The GUI provides visual configuration, build progress, and repository browsing.

### Command Line Examples

**Basic build and publish:**
```bash
python ig_publisher.py \
  --source ./my-ig-source \
  --enable-sparse
```

**Publish to GitHub Pages:**
```bash
python ig_publisher.py \
  --source ./my-ig-source \
  --publish-gh-pages \
  --sitepreview-dir "preview" \
  --exclude "ig-build-zips/" \
  --exclude "temp/"
```

**Create pull requests:**
```bash
python ig_publisher.py \
  --source ./my-ig-source \
  --enable-pr \
  --github-token "$GH_PAT"
```

**Custom repository configuration:**
```bash
python ig_publisher.py \
  --source-repo "https://github.com/your-org/your-ig" \
  --source-branch "develop" \
  --webroot-repo "https://github.com/your-org/templates" \
  --webroot-branch "staging" \
  --enable-sparse \
  --sparse templates assets css
```

### Publication Request Configuration

For formal IG publishing, ensure your IG has a `publication-request.json`:

```json
{
  "package-id": "your.org.ig.id",
  "version": "1.0.0",
  "path": "https://your-org.org/fhir/ig/1.0.0",
  "mode": "milestone",
  "status": "release", 
  "sequence": "Releases",
  "desc": "Initial release",
  "first": true,
  "title": "Your IG Title",
  "ci-build": "https://build.fhir.org/ig/your-org/your-ig",
  "category": "Infrastructure",
  "introduction": "Description of your IG"
}
```

Or use the `--ensure-pubreq` flag to auto-generate for CI builds.

## GitHub Actions Integration

### Reusable Workflow

```yaml
name: Publish IG

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to publish'
        required: false
        default: '1.0.0'

jobs:
  publish:
    uses: costateixeira/smart-html/.github/workflows/release.yml@main
    with:
      pubreq_package_id: ${{ github.event.inputs.version && format('your.org.ig.id#{0}', github.event.inputs.version) || 'your.org.ig.id' }}
      pubreq_version: ${{ github.event.inputs.version || '0.1.0-ci' }}
      pubreq_canonical: "https://your-org.org/fhir/ig"
      pubreq_path: ${{ github.event.inputs.version && format('https://your-org.org/fhir/ig/{0}', github.event.inputs.version) || 'https://build.your-org.org/fhir/ig' }}
      sitepreview_dir: "sitepreview"
    permissions:
      contents: write
```

### Repository Configuration

Create `.github/release-config.yaml` to override global settings:

```yaml
webroot_repo: https://github.com/your-org/your-templates
enable_sparse_checkout: true
sparse_dirs:
  - templates
  - your-custom-assets
enable_pr_creation: false  # Disable for CI builds
```

## Advanced Features

### Sparse Checkout

For large template repositories, sparse checkout improves clone performance:

```yaml
enable_sparse_checkout: true
sparse_dirs:
  - templates          # Always included
  - assets            # CSS, JS, images
  - css               # Stylesheets
  - js                # JavaScript
  - your-ig-name      # IG-specific folder
```

The tool automatically includes essential files:
- `templates/`
- `publish-setup.json`
- `package-registry.json`
- `package-feed.xml`
- `publication-feed.xml`

### GitHub Pages Publishing

Publish to GitHub Pages with file exclusions:

```bash
python ig_publisher.py \
  --publish-gh-pages \
  --sitepreview-dir "preview" \
  --gh-pages-branch "gh-pages" \
  --exclude "ig-build-zips/" \
  --exclude "temp/" \
  --exclude "qa/"
```

Features:
- Creates `gh-pages` branch if missing
- Manages `.gitignore` for large files
- Handles authentication via `GITHUB_TOKEN`
- Supports custom preview directories
- Excludes unwanted files/folders

### Pull Request Creation

Create PRs for webroot and IG registry updates:

```yaml
enable_pr_creation: true
webroot_pr_target_branch: main
registry_pr_target_branch: master
```

## Troubleshooting

### Common Issues

**Java Memory Issues:**
```bash
# Increase Java heap size
export JAVA_OPTS="-Xmx8g"
```

**Jekyll Build Failures:**
```bash
# Check Ruby/Jekyll installation
jekyll --version
bundle --version

# Install missing gems
bundle install
```

**Git Authentication:**
```bash
# For GitHub Actions
# GITHUB_TOKEN is automatically provided

# For local development  
export GH_PAT="your_personal_access_token"
```

**Sparse Checkout Issues:**
```bash
# Check sparse checkout configuration
git sparse-checkout list
git sparse-checkout reapply
```

### Debug Mode

Enable verbose logging:

```bash
# Set logging level
export PYTHONPATH=.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
python ig_publisher.py --source ./my-ig
```

### Build Verification

The tool verifies:
- Build output directory exists
- QA files are generated  
- Required templates are available
- Publication request is valid

## Development

### Project Structure

```
├── ig_publisher.py           # Main application
├── requirements.txt          # Python dependencies  
├── requirements-gui.txt      # GUI dependencies
├── release-config.yaml       # Configuration template
├── .github/
│   └── workflows/
│       └── release.yml       # Reusable workflow
└── docs/                     # Additional documentation
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/ -v --cov=ig_publisher
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 **Documentation**: [GitHub Wiki](https://github.com/costateixeira/smart-html/wiki)
- 🐛 **Issues**: [GitHub Issues](https://github.com/costateixeira/smart-html/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/costateixeira/smart-html/discussions)
- 🔗 **FHIR Community**: [chat.fhir.org](https://chat.fhir.org/#narrow/stream/179252-IG-creation)

## Acknowledgments

- HL7 FHIR Community for the IG Publisher tool
- Contributors and maintainers
