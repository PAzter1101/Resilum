#!/bin/bash
set -e

RUN_DOCKER=false
DOCKER_PROFILE="full"

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            RUN_DOCKER=true
            shift
            ;;
        --profile)
            DOCKER_PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--docker] [--profile lora|mesh|covert|full]"
            exit 1
            ;;
    esac
done

SOURCE_DIRS=(bridges/ scripts/ tests/)
LINT_DIRS=(bridges/ scripts/)

echo "🔍 Resilum Quality Check"
echo "========================"

echo "🐍 Picking Python interpreter..."
PYTHON=""
for candidate in python python3 python3.13 python3.12 python3.11; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    version=$("$candidate" --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    case "$version" in
        3.11|3.12|3.13)
            PYTHON="$candidate"
            echo "✓ Using $candidate (Python $version, matches CI matrix)"
            break
            ;;
    esac
done
if [ -z "$PYTHON" ]; then
    echo "❌ Error: need Python 3.11, 3.12 or 3.13 on PATH (tried: python python3.13 python3.12 python3.11)"
    exit 1
fi

echo ""
echo "📋 Step 1: Linting & Static Analysis"
echo "-------------------------------------"
echo "✓ Setting up linting environment..."
WANT_VERSION=$("$PYTHON" --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ -d .venv-check ]; then
    HAVE_VERSION=$(.venv-check/bin/python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [ "$HAVE_VERSION" != "$WANT_VERSION" ]; then
        echo "  → existing .venv-check is Python $HAVE_VERSION, recreating with $WANT_VERSION"
        rm -rf .venv-check
    fi
fi
"$PYTHON" -m venv .venv-check
# shellcheck source=/dev/null
source .venv-check/bin/activate
pip install --upgrade pip > /dev/null 2>&1
uv export --no-default-groups --group dev --no-emit-project --format requirements-txt 2>/dev/null \
    | pip install --require-hashes -r /dev/stdin > /dev/null 2>&1

if ! black --check "${SOURCE_DIRS[@]}" > /dev/null 2>&1; then
    echo "  → Fixing code formatting (black)..."
    black "${SOURCE_DIRS[@]}"
fi

echo "  → ruff (lint, import order, in-function imports; autofixes what it can)..."
ruff check --fix "${SOURCE_DIRS[@]}"

echo "  → mypy..."
mypy --ignore-missing-imports "${LINT_DIRS[@]}"

deactivate

echo ""
echo "🐚 Step 2: Shellcheck"
echo "---------------------"
if ! command -v shellcheck &> /dev/null; then
    echo "❌ shellcheck not installed"
    echo "   Arch:   sudo pacman -S shellcheck"
    echo "   Debian: sudo apt install shellcheck"
    exit 1
fi
shellcheck docker/*.sh check.sh
echo "✓ shellcheck passed"

echo ""
echo "🐳 Step 3: Container & Config Lint"
echo "----------------------------------"
# shellcheck source=/dev/null
source .venv-check/bin/activate
echo "  → yamllint (compose + config)..."
yamllint docker-compose.yml config/defaults/
deactivate

echo "  → hadolint (Dockerfile)..."
if command -v hadolint &> /dev/null; then
    hadolint docker/Dockerfile
elif command -v docker &> /dev/null && docker info &> /dev/null; then
    docker run --rm -i hadolint/hadolint:v2.14.0 hadolint - < docker/Dockerfile
else
    echo "    ⚠️  hadolint and docker both unavailable, skipping"
fi

echo "  → docker compose config (validate)..."
if command -v docker &> /dev/null && docker info &> /dev/null; then
    docker compose config -q && echo "    ✓ compose valid"
else
    echo "    ⚠️  docker unavailable, skipping"
fi

echo ""
echo "🧪 Step 4: Unit Tests"
echo "---------------------"
# shellcheck source=/dev/null
source .venv-check/bin/activate
pytest tests/unit -v
deactivate

echo ""
echo "💨 Step 5: Smoke Tests"
echo "----------------------"
# shellcheck source=/dev/null
source .venv-check/bin/activate
pytest tests/smoke -v
deactivate

if [ "$RUN_DOCKER" = true ]; then
    echo ""
    echo "🏗️  Step 6: Docker Build (profile=$DOCKER_PROFILE)"
    echo "----------------------------------------------"
    if command -v docker &> /dev/null && docker info &> /dev/null; then
        # `buildx --load` materialises the image in the local Docker
        # engine. `docker compose build` on Docker Desktop puts the
        # image into BuildKit's isolated cache only, which then makes
        # `compose up` fall back to pulling the published tag from
        # GHCR — i.e. the local rebuild silently does nothing.
        docker buildx build --load \
            -f docker/Dockerfile \
            --build-arg "PROFILE=$DOCKER_PROFILE" \
            -t "ghcr.io/pazter1101/resilum:$DOCKER_PROFILE" \
            -t "resilum:check-$DOCKER_PROFILE" \
            .
        echo "✓ Image built: resilum:check-$DOCKER_PROFILE (also tagged ghcr.io/pazter1101/resilum:$DOCKER_PROFILE for compose)"
    elif command -v podman &> /dev/null; then
        podman build -f docker/Dockerfile --build-arg "PROFILE=$DOCKER_PROFILE" -t "resilum:check-$DOCKER_PROFILE" .
        echo "✓ Image built: resilum:check-$DOCKER_PROFILE"
    else
        echo "⚠️  No container runtime available, skipping build"
    fi
else
    echo ""
    echo "⏭️  Skipping docker build (use --docker to run)"
fi

echo ""
echo "✅ All checks passed!"
