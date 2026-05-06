#!/usr/bin/env bash
# =============================================================================
#  setup-vex-sim.sh  —  VEX EXP Simulator Workspace Setup Script  (uv edition)
# =============================================================================
#
#  PURPOSE
#    Sets up a student's laptop so they can run the vex_sim simulator — a
#    simulator for VEX EXP Python programs.  Everything is installed into
#    an isolated virtual environment so nothing clashes with the rest of
#    the system.
#
#    Uses "uv" — a fast Python package manager — for all environment and
#    package operations.  If uv is not already installed, the script will
#    install it for you automatically.
#
#  USAGE
#    1. Open a terminal in the (empty) folder where you want your VEX work
#       to live, e.g.:
#              mkdir ~/vex && cd ~/vex
#    2. Download this script into that folder, then run:
#              bash setup-vex-sim.sh
#    3. After it finishes, run your starter program:
#              uv run python -m vex_sim run my_robot.py --render
#
#  WHAT THIS SCRIPT DOES (step by step)
#    1. Checks for uv — if missing, installs it automatically.
#    2. Configures the UV_NATIVE_TLS environment variable in your shell
#       profile so that uv always uses the system's TLS certificates.
#       This is needed to work through the school firewall.
#    3. Refuses to run inside the vex_sim source repo (a teacher / developer
#       working area) and points to the right command instead.
#    4. Uses uv to download / locate the pinned Python version.
#    5. Writes a tiny pyproject.toml that declares ONE dependency: the
#       vex_sim package, fetched as a tarball straight from GitHub.
#       The "render" extra is included so the on-screen window works.
#    6. Runs `uv sync` to create the .venv/ folder and install everything.
#    7. Runs a tiny smoke-test (`vex_sim list`) to confirm it all works.
#    8. Writes a starter student file (my_robot.py) so you can begin coding
#       straight away.
#    9. Prints a friendly summary with the exact commands to run next.
#
#  WHY A TARBALL URL INSTEAD OF GIT?
#    The dependency line in pyproject.toml looks like this:
#
#       vex_sim[render] @ https://github.com/mr-bev/vex_playground/archive/
#                         refs/heads/main.tar.gz
#
#    This tells uv: "download this .tar.gz from GitHub, build the wheel,
#    install it."  No git command is needed on the student's machine —
#    just an HTTPS download, the same kind that fetches any other package.
#    GitHub generates this tarball automatically for every branch.
#
#    When a new version is released, students re-run this script and uv
#    re-downloads the tarball (we use --refresh-package to defeat caching
#    so this always works).
#
#  NOTE ON --native-tls / UV_NATIVE_TLS
#    The school firewall intercepts HTTPS traffic using its own certificate.
#    By default uv uses its own bundled certificates and doesn't trust the
#    school's, causing SSL errors.  Setting UV_NATIVE_TLS=1 (or passing
#    --native-tls) tells uv to use the operating system's certificate store,
#    which *does* trust the school's certificate.
#
#    This script:
#      a) Adds  export UV_NATIVE_TLS=1  to your shell profile (~/.bashrc)
#         so every future terminal session has it automatically.
#      b) Sets the variable for the current script run so everything works
#         immediately without needing to restart your terminal.
#
#  REQUIREMENTS
#    - A Linux or macOS system (Ubuntu, Debian, Fedora, macOS, etc.)
#    - curl or wget (for installing uv if needed — almost always pre-installed)
#    - An internet connection
#
# =============================================================================

# ---------------------------------------------------------------------------
#  CONFIGURATION — Teachers: change these values to suit your class.
# ---------------------------------------------------------------------------

# The exact Python version students should use.  Pinning this ensures every
# student's environment behaves identically, which makes debugging much easier.
# uv will automatically download this version if it isn't already installed.
# vex_sim requires Python 3.10 or newer (see the project's pyproject.toml).
PINNED_PYTHON_VERSION="3.13"

# Where to fetch vex_sim from.  This points at a tagged release tarball,
# which is IMMUTABLE — the contents (and therefore the hash) never change
# for a given tag.  That means uv's lockfile stays valid across re-runs
# and we don't need to force-refresh anything.
#
# To bump students to a newer release, just change the tag below.  To pull
# whatever is on main instead (mutable, unstable), change to:
#     https://github.com/mr-bev/vex_playground/archive/refs/heads/main.tar.gz
# and add `--refresh-package vex_sim --upgrade-package vex_sim` to the
# `uv sync` call further down so re-runs don't fail with hash mismatches.
VEX_SIM_VERSION="v0.1.0"
VEX_SIM_TARBALL="https://github.com/mr-bev/vex_playground/archive/refs/tags/${VEX_SIM_VERSION}.tar.gz"

# The dependency line that goes into pyproject.toml.
# "vex_sim[render]" requests the optional "render" extra so pygame-ce is
# pulled in and the --render mode (on-screen window) works.
VEX_SIM_DEP="vex_sim[render] @ ${VEX_SIM_TARBALL}"

# The name of the virtual-environment folder uv will create.
# uv uses ".venv" by default — keeping this convention makes tooling happier.
VENV_DIR=".venv"

# ---------------------------------------------------------------------------
#  COLOUR HELPERS — make terminal output easier to read.
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'  # No Colour (reset)

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[  OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[FAIL]${NC}  $*"; }

# ---------------------------------------------------------------------------
#  STEP 0 — Say hello
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   vex_sim — Workspace Setup Script           ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ---------------------------------------------------------------------------
#  STEP 1 — Ensure uv is installed
# ---------------------------------------------------------------------------
# If uv is already on the PATH, great — we skip ahead.
# If not, we download and run the official install script from Astral.
#
# The install script places uv in ~/.local/bin (or ~/.cargo/bin on some
# systems).  We then add that directory to the PATH for the remainder of
# this script.  The installer also updates the student's shell profile so
# future terminal sessions will find uv automatically.
#
# Note: The install script uses curl (or wget) which both use the system's
# native TLS stack, so the school firewall is not a problem at this stage.

info "Looking for uv..."

if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version 2>&1)
    success "Found ${UV_VERSION}"
else
    warn "uv is not installed.  Installing it now..."

    # Try curl first (most common), fall back to wget.
    if command -v curl &> /dev/null; then
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh 2>&1; then
            error "Failed to install uv via curl."
            echo ""
            echo "  Check your internet connection and try again."
            exit 1
        fi
    elif command -v wget &> /dev/null; then
        if ! wget -qO- https://astral.sh/uv/install.sh | sh 2>&1; then
            error "Failed to install uv via wget."
            echo ""
            echo "  Check your internet connection and try again."
            exit 1
        fi
    else
        error "Neither 'curl' nor 'wget' was found."
        echo ""
        echo "  Install one of them first, then re-run this script:"
        echo ""
        echo "    sudo apt install curl"
        echo ""
        exit 1
    fi

    # The uv installer puts the binary in one of these locations.
    # Add both to PATH so we can find it immediately without restarting
    # the terminal.
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    # Verify that uv is now available.
    if ! command -v uv &> /dev/null; then
        error "uv was installed but could not be found on PATH."
        echo ""
        echo "  Try closing and re-opening your terminal, then run this script again."
        exit 1
    fi

    UV_VERSION=$(uv --version 2>&1)
    success "Installed ${UV_VERSION}"
fi

# ---------------------------------------------------------------------------
#  STEP 2 — Configure UV_NATIVE_TLS for the school firewall
# ---------------------------------------------------------------------------
# We need to do two things:
#   a) Export the variable RIGHT NOW so the rest of this script works.
#      Every uv command in this script ALSO passes --native-tls explicitly
#      as belt-and-braces, in case the env var is dropped for any reason.
#   b) Add it to the student's shell profile so every future terminal has it
#      (so commands like `uv run ...` work after this script finishes).
#
# Step (b) needs to write to the profile that the student's actual login
# shell will read.  Picking "the first file that exists" is wrong: on a
# zsh user's machine, .bashrc may exist (left over from old setups) but
# zsh will never read it.  Instead, we pick based on $SHELL.

info "Configuring UV_NATIVE_TLS for the school firewall..."

# (a) Set it for the current script run immediately.
export UV_NATIVE_TLS=1

# (b) Persist it in the student's shell profile.
#     We pick the profile that matches the student's actual login shell.
#       zsh    → ~/.zshrc
#       bash   → ~/.bashrc on Linux, ~/.bash_profile on macOS
#                (macOS bash login shells don't read .bashrc by default)
#       other  → ~/.profile if present, else ~/.bashrc as a sensible default
SHELL_PROFILE=""
case "$(basename "${SHELL:-/bin/bash}")" in
    zsh)
        SHELL_PROFILE="$HOME/.zshrc"
        ;;
    bash)
        if [[ "$(uname)" == "Darwin" ]]; then
            SHELL_PROFILE="$HOME/.bash_profile"
        else
            SHELL_PROFILE="$HOME/.bashrc"
        fi
        ;;
    *)
        if [ -f "$HOME/.profile" ]; then
            SHELL_PROFILE="$HOME/.profile"
        else
            SHELL_PROFILE="$HOME/.bashrc"
        fi
        ;;
esac

# The exact line we want in the profile.
UV_TLS_LINE='export UV_NATIVE_TLS=1  # Use system TLS certs (school firewall)'

# Only add the line if it isn't already present.
if grep -qF "UV_NATIVE_TLS=1" "$SHELL_PROFILE" 2>/dev/null; then
    success "UV_NATIVE_TLS already set in ${SHELL_PROFILE}"
else
    # Append a blank line first for readability, then the export.
    {
        echo ""
        echo "# Added by setup-vex-sim.sh — allows uv to work through the school firewall."
        echo "$UV_TLS_LINE"
    } >> "$SHELL_PROFILE"
    success "Added UV_NATIVE_TLS=1 to ${SHELL_PROFILE}"
fi

# ---------------------------------------------------------------------------
#  STEP 3 — Refuse to run inside the vex_sim source repo
# ---------------------------------------------------------------------------
# If a teacher / developer accidentally runs this script inside the actual
# vex_playground source tree, it would shadow the project's own pyproject.toml
# and create confusion.  Detect that and bail with a helpful message.

if [ -f "pyproject.toml" ] && grep -q '^name = "vex_sim"' pyproject.toml 2>/dev/null; then
    error "This folder IS the vex_sim source repo."
    echo ""
    echo "  setup-vex-sim.sh is meant for STUDENTS who want to USE vex_sim."
    echo "  You appear to be sitting inside the project being developed."
    echo ""
    echo "  To set up a developer environment instead, run:"
    echo ""
    echo "    uv sync --extra render"
    echo ""
    echo "  Or, to use this script the way a student would, make a fresh empty"
    echo "  folder somewhere else, copy the script there, and run it from there."
    echo ""
    exit 1
fi

# ---------------------------------------------------------------------------
#  STEP 4 — Ensure the pinned Python version is available
# ---------------------------------------------------------------------------
# uv can download and manage Python installations for us.  If the pinned
# version isn't already on the machine, this command will fetch it.
# UV_NATIVE_TLS is already set, so uv will use system TLS certificates
# automatically — no need for the --native-tls flag on every command.

info "Ensuring Python ${PINNED_PYTHON_VERSION} is available..."

# --native-tls is passed explicitly (not just via UV_NATIVE_TLS env var) so
# this works even in a sub-shell where the env var hasn't been picked up yet.
if ! uv --native-tls python install "$PINNED_PYTHON_VERSION" 2>&1; then
    error "Failed to install Python ${PINNED_PYTHON_VERSION} via uv."
    echo ""
    echo "  Check your internet connection and try again."
    exit 1
fi

success "Python ${PINNED_PYTHON_VERSION} is ready."

# ---------------------------------------------------------------------------
#  STEP 5 — Write a minimal pyproject.toml
# ---------------------------------------------------------------------------
# This pyproject.toml describes the student's WORKSPACE, not a library they
# are publishing.  The single dependency is the vex_sim package, fetched
# from GitHub as a tarball.
#
# `package = false` under [tool.uv] tells uv "this project doesn't itself
# build a wheel — it's just a folder for managing dependencies."  Without
# this, uv would try to package the student's folder as a Python project
# and fail because there is no source code to package.
#
# If a pyproject.toml already exists, we leave it alone — the student may
# have edited it (e.g. to add other dependencies for their own experiments).

PYPROJECT_FILE="pyproject.toml"

if [ -f "$PYPROJECT_FILE" ]; then
    info "${PYPROJECT_FILE} already exists — leaving it as-is."
    # Warn if the existing pyproject is pinned to a different version of
    # vex_sim than this script expects (e.g. an old script run pinned an
    # older tag).  A re-run won't pick up the new version on its own; the
    # student needs to wipe pyproject.toml + uv.lock to upgrade.
    if ! grep -qF "${VEX_SIM_VERSION}.tar.gz" "$PYPROJECT_FILE" 2>/dev/null; then
        warn "  Your ${PYPROJECT_FILE} is pinned to a different vex_sim version"
        warn "  than this script (${VEX_SIM_VERSION}).  To upgrade, run:"
        warn "      rm ${PYPROJECT_FILE} uv.lock"
        warn "  then re-run this script."
    fi
else
    info "Writing ${PYPROJECT_FILE}..."
    cat > "$PYPROJECT_FILE" << PYPROJECT_EOF
# pyproject.toml — your VEX simulator workspace.
#
# This file tells uv which Python version and which packages your project
# needs.  setup-vex-sim.sh wrote it for you.  You can edit it to add more
# packages later — for example, if you want to plot data with matplotlib,
# add  "matplotlib"  to the dependencies list and run  uv sync  again.

[project]
name = "vex-student-workspace"
version = "0.1.0"
description = "Student workspace for the vex_sim simulator"
requires-python = ">=${PINNED_PYTHON_VERSION}"
dependencies = [
    "${VEX_SIM_DEP}",
]

[tool.uv]
# This project is just a workspace, not a package being published.
package = false
PYPROJECT_EOF
    success "Wrote ${PYPROJECT_FILE}"
fi

# ---------------------------------------------------------------------------
#  STEP 6 — Create the virtual environment and install everything
# ---------------------------------------------------------------------------
# `uv sync` does three things in one go:
#   1. Creates the .venv/ folder (or reuses it if it already exists).
#   2. Installs the pinned Python interpreter.
#   3. Installs every dependency from pyproject.toml.
#
# We pass --refresh-package vex_sim so uv always re-downloads the tarball
# from GitHub.  Without this, uv would happily reuse a cached copy from a
# previous run and the student would never see updates from the repo.
#
# If the student already has a stale .venv from an old version of the
# project, offer to wipe and rebuild it cleanly.

if [ -d "$VENV_DIR" ]; then
    warn "An existing '${VENV_DIR}' folder was found."
    read -rp "     Wipe it and rebuild from scratch? (y/N): " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        info "Removed old ${VENV_DIR}/ folder."
    else
        info "Keeping existing environment.  uv sync will update it in place."
    fi
fi

info "Installing vex_sim ${VEX_SIM_VERSION} and its dependencies (this may take a minute)..."

# --native-tls : explicit flag so we don't depend on UV_NATIVE_TLS being
#                live in this shell.
#
# We pin to a tagged release (see VEX_SIM_VERSION at the top of the
# script), so the tarball is immutable.  That means re-running this
# script is a fast no-op once everything is installed — uv compares the
# locked hash, finds it matches, and does nothing.  No --refresh-package
# / --upgrade-package needed.
if ! uv --native-tls sync --python "$PINNED_PYTHON_VERSION" 2>&1; then
    error "uv sync failed.  Check the output above for details."
    echo ""
    echo "  Common causes:"
    echo "    - No internet connection."
    echo "    - School firewall blocking the package index."
    echo "      (UV_NATIVE_TLS should fix this — close and re-open your terminal,"
    echo "      then run this script again.)"
    echo "    - GitHub is unreachable from this network."
    exit 1
fi

success "All dependencies installed."

# ---------------------------------------------------------------------------
#  STEP 7 — Smoke-test the simulator
# ---------------------------------------------------------------------------
# `vex_sim list` enumerates the bundled playgrounds.  If this command works,
# the package is importable, the playground files are on disk, and the
# CLI entry point is wired up correctly.

info "Running a quick smoke-test (vex_sim list)..."

if ! uv run python -m vex_sim list > /dev/null 2>&1; then
    error "Smoke-test failed: 'python -m vex_sim list' did not run cleanly."
    echo ""
    echo "  Try running it yourself to see the full error:"
    echo "    uv run python -m vex_sim list"
    exit 1
fi

success "Simulator imports and runs."

# Capture version strings for the summary at the end.
VENV_PYTHON="${VENV_DIR}/bin/python"
FULL_VERSION=$("$VENV_PYTHON" --version 2>&1)
PYGAME_CE_VERSION=$("$VENV_PYTHON" -c "import pygame; print(pygame.ver)" 2>/dev/null)

# ---------------------------------------------------------------------------
#  STEP 8 — Create a starter student file (if one doesn't exist already)
# ---------------------------------------------------------------------------
# This gives students something to run within seconds of finishing setup.
# We only write the file if it does not already exist, so we never clobber
# a student's in-progress work.

STARTER_FILE="my_robot.py"

if [ ! -f "$STARTER_FILE" ]; then
    info "Creating a starter file: ${STARTER_FILE}"
    cat > "$STARTER_FILE" << 'STARTER_EOF'
# my_robot.py — your first VEX EXP simulator program.
#
# Run headless (no window):
#     uv run python -m vex_sim run my_robot.py
#
# Run with the on-screen window:
#     uv run python -m vex_sim run my_robot.py --render
#
# Try a different playground:
#     uv run python -m vex_sim run my_robot.py --playground low_wall_maze --render
#
# List every bundled playground:
#     uv run python -m vex_sim list --verbose

from vex import *

brain = Brain()

# Two motors driving the wheels.  PORT6 is the left wheel; PORT10 is the
# right wheel.  The "True" on the right motor reverses it so both wheels
# spin forward when the drivetrain drives forward.
left_drive  = Motor(Ports.PORT6,  False)
right_drive = Motor(Ports.PORT10, True)

# A drivetrain ties the two motors together so we can give it instructions
# in millimetres and degrees instead of motor RPM.
#   wheel circumference = 259.34 mm
#   track width         = 320   mm  (distance between left and right wheel)
#   wheel base          = 40    mm
drivetrain = DriveTrain(left_drive, right_drive, 259.34, 320, 40, MM, 1)

drivetrain.set_drive_velocity(60, PERCENT)
drivetrain.set_turn_velocity(60, PERCENT)

# Drive forward 500 mm, turn right 90 degrees, then stop.
drivetrain.drive_for(FORWARD, 500, MM)
drivetrain.turn_for(RIGHT, 90, DEGREES)
drivetrain.stop()

brain.screen.print("Hello from my_robot.py!")
STARTER_EOF
    success "Starter file created: ${STARTER_FILE}"
else
    info "${STARTER_FILE} already exists — leaving it as-is."
fi

# ---------------------------------------------------------------------------
#  DONE — Print a friendly summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Setup complete!  You're ready to code.     ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Python    :${NC}  ${FULL_VERSION}"
if [ -n "$PYGAME_CE_VERSION" ]; then
    echo -e "  ${BOLD}pygame-ce :${NC}  ${PYGAME_CE_VERSION}"
fi
echo -e "  ${BOLD}venv      :${NC}  $(pwd)/${VENV_DIR}/"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo ""
echo -e "    1. Run your starter program with the on-screen window:"
echo ""
echo -e "         ${YELLOW}uv run python -m vex_sim run ${STARTER_FILE} --render${NC}"
echo ""
echo -e "    2. Or run it headless (just prints a JSON result):"
echo ""
echo -e "         ${YELLOW}uv run python -m vex_sim run ${STARTER_FILE}${NC}"
echo ""
echo -e "    3. See every bundled playground / scenario:"
echo ""
echo -e "         ${YELLOW}uv run python -m vex_sim list --verbose${NC}"
echo ""
echo -e "    4. Open ${STARTER_FILE} in your editor and start experimenting!"
echo ""
echo -e "    Tip: ${BOLD}uv run${NC} automatically activates the .venv for you,"
echo -e "    so you do not need to source ${VENV_DIR}/bin/activate manually."
echo ""
echo -e "    To get the latest version of vex_sim later, just re-run this script."
echo ""
