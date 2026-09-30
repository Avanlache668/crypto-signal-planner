# Publish a NEW public GitHub repository

Publishing makes every tracked file visible to everyone. Review file content before proceeding. This package intentionally contains no brokerage keys, credentials or real trades, and does not set a reuse license.

1. Install Git and [GitHub CLI](https://cli.github.com/) on your own machine.
2. Authenticate with `gh auth login` (never paste a token in issues, commits or chat).
3. Extract this prepared repository directory and enter it.
4. Confirm that `crypto-signal-planner` does not already exist in your selected account.
5. Run:

```bash
CONFIRM_PUBLIC=1 bash publish_github.sh
```

The script validates the local smoke test, initializes a repository on `main` only if necessary, commits files using **your own configured Git author identity**, checks GitHub authentication and repository-name availability, creates a NEW public repository, sets `origin`, and pushes. It refuses to publish if an `origin` remote already exists, the working tree is dirty, or the intended repository already exists. To publish under an organization, set `GH_OWNER=your-org`.

Manual equivalent after `git init`, `git add`, `git commit`:

```bash
gh repo create crypto-signal-planner --public --source=. --remote=origin --push
```

If you want others to reuse/modify/distribute the code, choose and add an explicit `LICENSE` after reviewing its terms.

## Push into an existing repository

If `Avanlache668/crypto-signal-planner` already exists (with an initial README), run from this package's root:

```bash
# Requires gh auth login and push permission to the repository
CONFIRM_PUBLIC=1 bash push_existing_github.sh
```

The script validates offline checks, clones the existing repository, adds only the allowlisted skill source files, creates a normal commit, and pushes without rewriting history. Use `GH_REPO=owner/repo` to publish to a different existing public repository. Never put credentials or broker account exports into the source directory.
