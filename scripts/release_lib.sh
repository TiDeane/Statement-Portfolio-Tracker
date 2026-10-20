# Shared by scripts/release_candidate.sh and scripts/release.sh, which follow RELEASING.md. Not run on its own.
# Run in WSL, from anywhere in the repository; both scripts need git and the GitHub CLI (gh), signed in.

set -euo pipefail

DRY_RUN=0
DOWNLOADS=""

say() { printf '\n== %s\n' "$*"; }
note() { printf '   %s\n' "$*"; }
fail() { printf '\nStopped: %s\n' "$*" >&2; exit 1; }

# Run a command that changes something (a commit, a push, a tag, a deletion), or, in a dry run, only show it.
act() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '   (dry run, not done) %s\n' "$*"
  else
    "$@"
  fi
}

confirm() {  # confirm QUESTION: yes or no from the keyboard; a dry run says yes without asking
  if [ "$DRY_RUN" = 1 ]; then
    printf '   (dry run) %s yes\n' "$1"
    return 0
  fi
  local answer
  read -r -p "   $1 [y/N] " answer
  [ "$answer" = y ] || [ "$answer" = Y ]
}

parse_options() {  # parse_options "$@": --dry-run, --downloads DIR, --next X.Y.Z
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run) DRY_RUN=1 ;;
      --downloads) DOWNLOADS="${2:?--downloads needs a folder}"; shift ;;
      --next) NEXT="${2:?--next needs a version, such as 1.3.0}"; shift ;;
      -h|--help) sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
      *) fail "unknown option $1 (see --help)" ;;
    esac
    shift
  done
}

# The repository, its release branch and the version it is named after: release/1.2.0 is version 1.2.0.
start() {
  cd "$(git rev-parse --show-toplevel)"
  command -v gh > /dev/null || fail "the GitHub CLI (gh) is not installed."
  gh auth status > /dev/null 2>&1 || fail "the GitHub CLI is not signed in: run gh auth login."
  BRANCH="$(git branch --show-current)"
  [[ "$BRANCH" =~ ^release/([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] \
    || fail "this runs on a release branch such as release/1.2.0; the current branch is '${BRANCH:-none}'."
  VERSION="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
  NEXT="${NEXT:-${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.$((BASH_REMATCH[3] + 1))}"
  say "Release branch $BRANCH, version $VERSION$([ "$DRY_RUN" = 1 ] && echo ', dry run: nothing is pushed or changed')"
  # What is released is what is committed: changes left uncommitted would silently not be in it.
  if ! git diff --quiet || ! git diff --cached --quiet; then
    [ "$DRY_RUN" = 1 ] || fail "there are changes not committed: commit them, or put them aside (git stash), first."
    note "Not committed, so a real run would stop here (a dry run goes on):"
    git status --short --untracked-files=no | sed 's/^/     /'
  fi
  git fetch --quiet --tags origin
}

app_version() {
  sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/statement_tracker/__init__.py
}

candidates() {  # the version's pre-release tags, here or on GitHub, oldest first: v1.2.0-rc1 v1.2.0-rc2 ...
  { git tag -l "v$VERSION-rc*"; git ls-remote --tags --refs origin "v$VERSION-rc*" | sed 's#.*refs/tags/##'; } \
    | grep -E "^v$VERSION-rc[0-9]+$" | sort -u -V || true
}

find_run() {  # find_run WORKFLOW REF COMMIT: the newest GitHub Actions run of WORKFLOW for REF at COMMIT, or nothing
  gh run list --workflow "$1" --limit 30 --json databaseId,headSha,headBranch \
    --jq ".[] | select(.headSha == \"$3\" and .headBranch == \"$2\") | .databaseId" | head -n 1
}

# wait_for_run WORKFLOW REF COMMIT: find the GitHub Actions run of WORKFLOW for REF (a branch or a tag) at COMMIT,
# follow it until it ends, and stop the script with its failed steps' log if it fails.
wait_for_run() {
  local workflow="$1" ref="$2" commit="$3" run="" waited=0
  if [ "$DRY_RUN" = 1 ]; then
    note "(dry run, not done) wait for '$workflow' on $ref"
    return 0
  fi
  note "Waiting for GitHub to start '$workflow' on $ref..."
  while [ -z "$run" ]; do
    run="$(find_run "$workflow" "$ref" "$commit")"
    if [ -z "$run" ]; then
      [ "$waited" -lt 180 ] || fail "'$workflow' did not start on $ref within 3 minutes: look at the Actions tab."
      sleep 5
      waited=$((waited + 5))
    fi
  done
  if ! gh run watch "$run" --exit-status --interval 15; then
    note "What failed:"
    gh run view "$run" --log-failed 2>/dev/null | tail -n 40 || true
    fail "'$workflow' failed on $ref. Details: $(gh run view "$run" --json url --jq .url)"
  fi
  note "'$workflow' passed on $ref."
}

windows_downloads() {  # the Windows user's Downloads folder, as WSL sees it; empty outside WSL
  local profile
  profile="$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')" || return 0
  [ -n "$profile" ] && wslpath "$profile\\Downloads" 2>/dev/null || true
}
