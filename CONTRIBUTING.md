# Contributing to django-vrt

First off, thank you for considering contributing. It's people like you that make `django-vrt` such a great tool.

## Development Environment

To get started with development, you'll need to set up your local environment.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/William-Blackie/django-vrt.git
    cd django-vrt
    ```

2.  **Install dependencies:**
    This project uses `uv` for dependency management. Install the development dependencies, including `playwright`.
    ```bash
    uv sync --extra dev
    uv run playwright install chromium
    ```

## Running Tests and Linting

Before submitting a pull request, please ensure that all tests and linting checks pass.

-   **Run tests:**
    ```bash
    uv run pytest
    ```

-   **Run linter:**
    ```bash
    uv run ruff check .
    ```

-   **Check test coverage:**
    ```bash
    make coverage
    ```

## Building the Documentation

The documentation is built using `MkDocs`. To preview your changes locally:

1.  **Install documentation dependencies:**
    ```bash
    uv pip install -r docs/requirements.txt
    ```

2.  **Serve the documentation:**
    ```bash
    mkdocs serve
    ```
    You can now view the documentation at `http://localhost:8000`.

## Release Process (for maintainers)

`django-vrt` is automatically published to PyPI via GitHub Actions. There are three ways to trigger a release:

### 1. **GitHub Release (Recommended)**
Create a new release through the GitHub UI:
1. Go to Releases → "Create a new release"
2. Set tag (e.g., `v0.2.0`) and title
3. Click "Publish release"
4. The workflow automatically builds and publishes to PyPI

### 2. **Version Tag Push**
Push a version tag directly:
```bash
git tag v0.2.0
git push origin v0.2.0
```
This triggers the build and publish automatically.

### 3. **Manual Workflow Trigger**
Run the publish workflow manually from GitHub:
1. Go to Actions → "publish" workflow
2. Click "Run workflow" → "Run workflow"
3. The current `main` branch code is built and published

### Pre-release checklist
Before releasing:
- Create or verify the release tag (`vX.Y.Z`) for `hatch-vcs` versioning
- Update `CHANGELOG.md` or release notes (if applicable)
- Ensure all tests pass: `uv sync --extra dev && uv run pytest`
- Verify linting: `uv run ruff check .`
- Verify coverage gate: `make coverage` (fails below configured threshold)
- Commit and push changes to `main`
