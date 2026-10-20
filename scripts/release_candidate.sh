#!/usr/bin/env bash
# Make a pre-release (a release candidate) of the release branch you are on, as RELEASING.md describes, and
# download its Windows installer so that you can test it.
#
#   bash scripts/release_candidate.sh [--dry-run] [--downloads FOLDER]
#
# Run it in WSL, on the version's branch (release/1.2.0 makes v1.2.0-rc1, then -rc2 ...). It:
#   1. checks the branch: nothing left uncommitted, and nothing on GitHub's main that the branch lacks;
#   2. sets the app's version to the branch's, with a commit, if it is not yet (it asks first);
#   3. runs the tests here, pushes the branch, and waits for GitHub's tests to pass on it;
#   4. tags the next pre-release, pushes the tag, and waits for the build of every system to pass;
#   5. downloads the Windows installer to your Downloads folder (or FOLDER).
# Then install it over the current version and do the checks in RELEASING.md; if they pass, run
# scripts/release.sh. If something must be fixed, commit the fix and run this again: it makes the next -rc.
#
# --dry-run shows each step, and what it would push or change, without doing it.

here="$(dirname "$0")"
source "$here/release_lib.sh"
parse_options "$@"
start

say "1. The branch"
git merge-base --is-ancestor origin/main HEAD \
  || fail "GitHub's main has commits this branch lacks. Bring them in first: git rebase origin/main, then run this again."
note "It has everything on GitHub's main."

say "2. The version"
if [ "$(app_version)" = "$VERSION" ]; then
  note "The app is already version $VERSION."
else
  note "The app says version $(app_version); this branch is for $VERSION."
  confirm "Set it to $VERSION and commit that?" || fail "the app's version must be $VERSION before a pre-release."
  act sed -i "s/^__version__ = \".*\"\$/__version__ = \"$VERSION\"/" src/statement_tracker/__init__.py
  act git add src/statement_tracker/__init__.py
  act git commit -m "chore: set the version to $VERSION"
fi

say "3. The tests"
if [ -x .venv/bin/python ]; then
  .venv/bin/python -m pytest -q || fail "the tests fail here: fix them before making a pre-release."
else
  note "No .venv here, so the tests run on GitHub only."
fi
act git push -u origin "$BRANCH"
wait_for_run "Tests" "$BRANCH" "$(git rev-parse HEAD)"

say "4. The pre-release build"
last="$(candidates | tail -n 1)"
number=$(( ${last##*-rc} + 1 ))
[ -n "$last" ] || number=1
TAG="v$VERSION-rc$number"
if [ -n "$last" ] && [ "$(git rev-parse "$last^{commit}" 2>/dev/null)" = "$(git rev-parse HEAD)" ]; then
  note "$last is already on this commit; making $TAG anyway would build the same thing again."
  confirm "Make $TAG all the same?" || fail "nothing new to build: test $last, or commit a fix first."
fi
note "Making $TAG."
act git tag "$TAG"
act git push origin "$TAG"
wait_for_run "Release build" "$TAG" "$(git rev-parse HEAD)"

say "5. The Windows installer"
folder="${DOWNLOADS:-$(windows_downloads)}"
folder="${folder:-dist/release-candidates}"
act mkdir -p "$folder"
act gh release download "$TAG" --pattern '*-windows-x64-setup.exe' --dir "$folder" --clobber
installer="$folder/StatementPortfolioTracker-$VERSION-windows-x64-setup.exe"
shown="$(wslpath -w "$installer" 2>/dev/null || echo "$installer")"
note "The installer: $shown"
note "The other systems' files: gh release view $TAG --web"

say "Ready to test"
note "Install $TAG over the current version, then go through the checks in RELEASING.md."
note "When they pass:      bash scripts/release.sh"
note "If something is wrong: commit the fix on $BRANCH, and run this again for the next pre-release."
