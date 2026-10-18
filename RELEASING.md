# Releasing

The automated tests work out the spreadsheet's formulas with a small imitation of Excel, and never open Excel itself. These checks, about ten minutes in real Excel on Windows, cover what only Excel can show. Do them on the pre-release build (a `-rc` tag), installed over the current version.

## 1. The installed app

- [ ] It opens, and **Settings** still lists your investments, with the names you gave them.
- [ ] **About and privacy** shows the new version number.

## 2. A spreadsheet with a missing value

In a scratch folder, not your real spreadsheet:

- [ ] Choose `samples/unpriced_investment.csv`, then **Create a new one...**, and press the green button. Pick the first listing for EQQB; skip ZQXJ.
- [ ] Open the file in Excel. In **Current Holdings**, the ZQXJ row is grey and its Current Value reads "unavailable" in red. The Total covers EQQB only, and the percentages show with a % sign.
- [ ] In **Portfolio History**, today's row is light orange, with a comment on its date saying it leaves out ZQXJ.
- [ ] Type `400` over "unavailable". The row turns black, the Total and the percentages follow at once, and today's history row follows too and loses its orange.
- [ ] Save, close Excel, and press the green button again. ZQXJ shows 400.00 marked "(your value)".

## 3. A long history

- [ ] Choose `samples/long_history.csv` with another new spreadsheet, and choose "Always choose the first option" when asked.
- [ ] In Excel, no cell shows an error such as `#VALUE!` or `#NAME?`; ROI %, Net Worth and Gain vs Deposits have values; every column is wide enough for its text.

## 4. Your own workbook

On a **copy** of your real spreadsheet:

- [ ] Run the app on it. Your own sheets, tables and charts look as before, and charts that read the app's sheets show today's figures.

## How to release

Pushing a tag that starts with `v` makes GitHub build the app for each system, test it, and publish it on the Releases page. The tag must be `v` and the app's version, optionally followed by a suffix, or the build stops: for version 1.1.0, `v1.1.0` or `v1.1.0-rc1`. A tag with a suffix is published as a pre-release, one without as the release everyone downloads.

All the work for the next version is committed on a branch named after it, such as `release/1.1.0`, never on `main`. `main` only ever gets a branch whose pre-release has passed the checks above. The commands below run in WSL, in the repository.

### 1. The branch

1. Make the branch once, from GitHub's `main`, and commit all the work for the version there:

   ```
   git fetch origin
   git checkout -b release/1.1.0 origin/main
   ```

   Push it whenever you like (`git push -u origin release/1.1.0` the first time, `git push` after that): GitHub runs the tests on every push.

2. When the work is done, set the version in `src/statement_tracker/__init__.py`, for example `__version__ = "1.1.0"`, and commit it:

   ```
   git add src/statement_tracker/__init__.py
   git commit -m "chore: set the version to 1.1.0"
   ```

3. Push the branch, and open a pull request into `main`. The tests must pass on it before going on.

   ```
   git push -u origin release/1.1.0
   gh pr create --base main --title "Release 1.1.0" --fill
   ```

### 2. A pre-release build to test (`-rc`)

1. Tag the branch's latest commit, and push the tag:

   ```
   git tag v1.1.0-rc1
   git push origin v1.1.0-rc1
   ```

2. Wait for the build to finish, on the repository's **Actions** tab or with `gh run watch`. It appears on the Releases page marked **Pre-release**.
3. Download the file ending in `-windows-x64-setup.exe` from that pre-release, install it over the current version, and go through the checks above.
4. If something is wrong, fix it on the branch, commit, push the branch, and tag again with the next number: `v1.1.0-rc2`.

### 3. The release

When a pre-release passes every check, make GitHub's `main` the branch as it is, so that it ends on the very commit that was tested:

```
git push origin release/1.1.0:main
```

GitHub then marks the pull request as merged by itself. (Its **Rebase and merge** button would not do: it makes new commits, so the commit tested would not be the one released.) The push is refused if `main` changed since the branch was made; then bring those changes into the branch (`git fetch origin`, `git rebase origin/main`, `git push --force-with-lease`), and go back to step 2 for a new pre-release.

Then tag the commit of the pre-release that passed without the suffix, and push the tag:

```
git tag v1.1.0 v1.1.0-rc1
git push origin v1.1.0
```

(`v1.1.0-rc1` there is the pre-release that passed.) The build runs again and publishes the release.

Finally, start the next version's branch where this one ends, and delete this one, here and on GitHub:

```
git checkout -b release/1.2.0
git branch -d release/1.1.0
git push origin --delete release/1.1.0
```

If the next version turns out to be another number, rename its branch: `git branch -m release/1.1.1`.

The pre-releases stay on the Releases page, marked as such, and the link to the latest release skips them. To remove them, each with its tag:

```
gh release delete v1.1.0-rc1 --cleanup-tag --yes
```
