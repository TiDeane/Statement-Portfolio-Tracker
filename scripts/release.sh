#!/usr/bin/env bash
# Publish the release once its last pre-release has passed the checks in RELEASING.md, then clean up.
#
#   bash scripts/release.sh [--dry-run] [--next X.Y.Z]
#
# Run it in WSL, on the version's branch, after scripts/release_candidate.sh and your checks. It:
#   1. checks that the branch is exactly the last pre-release's commit, and asks whether it passed the checks;
#   2. makes GitHub's main that commit (refused if main changed since the branch was made);
#   3. tags the release on it, pushes the tag, and waits for the build to publish it;
#   4. deletes the version's pre-releases and their tags, here and on GitHub;
#   5. starts the next version's branch where this one ends (release/X.Y.Z+1, or --next X.Y.Z), deletes this
#      one here and on GitHub, and brings the local main up to date.
#
# --dry-run shows each step, and what it would push or change, without doing it.

here="$(dirname "$0")"
source "$here/release_lib.sh"
parse_options "$@"
start

say "1. The pre-release that was tested"
CANDIDATE="$(candidates | tail -n 1)"
[ -n "$CANDIDATE" ] || fail "there is no pre-release of $VERSION: run scripts/release_candidate.sh first."
commit="$(git rev-parse "$CANDIDATE^{commit}")"
[ "$commit" = "$(git rev-parse HEAD)" ] \
  || fail "the branch has commits since $CANDIDATE, so they were never tested: run scripts/release_candidate.sh for a new pre-release."
gh release view "$CANDIDATE" > /dev/null 2>&1 \
  || fail "$CANDIDATE has no pre-release on GitHub (did its build fail?): run scripts/release_candidate.sh again."
[ "$(app_version)" = "$VERSION" ] || fail "the app says version $(app_version), not $VERSION."
TAG="v$VERSION"
git rev-parse -q --verify "refs/tags/$TAG" > /dev/null && fail "$TAG already exists: this version was released."
note "$CANDIDATE, on $(git log -1 --format='%h %s' "$commit")."
confirm "Did $CANDIDATE pass every check in RELEASING.md?" || fail "release only a pre-release that passed the checks."

say "2. GitHub's main"
git merge-base --is-ancestor origin/main HEAD \
  || fail "GitHub's main changed since the branch was made: git rebase origin/main, push with --force-with-lease, and make a new pre-release."
act git push origin "$BRANCH:main"

say "3. The release"
act git tag "$TAG" "$CANDIDATE"
act git push origin "$TAG"
wait_for_run "Release build" "$TAG" "$commit"
if [ "$DRY_RUN" = 0 ]; then
  url="$(gh release view "$TAG" --json url --jq .url)" || fail "the build passed, but no release $TAG is on GitHub."
  note "Published: $url"
fi

say "4. The pre-releases"
for candidate in $(candidates); do
  if gh release view "$candidate" > /dev/null 2>&1; then
    act gh release delete "$candidate" --cleanup-tag --yes
  elif git ls-remote --exit-code --tags origin "refs/tags/$candidate" > /dev/null; then
    act git push origin --delete "$candidate"  # a tag whose build failed, so it never became a release
  fi
  ! git rev-parse -q --verify "refs/tags/$candidate" > /dev/null || act git tag -d "$candidate"
done

say "5. The branches"
act git checkout -b "release/$NEXT"
act git branch -D "$BRANCH"  # all of it is on GitHub's main now
if git ls-remote --exit-code --heads origin "$BRANCH" > /dev/null; then
  act git push origin --delete "$BRANCH"
fi
act git fetch origin main:main

say "Released $TAG"
note "Work for the next version goes on release/$NEXT. If it turns out to be another number: git branch -m release/X.Y.Z"
