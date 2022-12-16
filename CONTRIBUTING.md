# Contributing

Contributions to this repository are welcome. To make a contribution we ask that you follow a few guidelines.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Issues and features](#issues-and-features)
- [Pull requests](#pull-requests)
- [Commit messages](#commit-messages)
  - [Commit Message Format](#commit-message-format)
    - [Type](#type)
    - [Subject](#subject)
    - [Body](#body)
    - [Footer](#footer)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Issues and features

Before filing a bug report or making a feature request, please check the issues to make sure yours isn't a duplicate.

## Pull requests

Feel free to submit pull requests to the `develop` branch with small fixes or improvements. Before implementing new features or contributing broadly-scoped changes we ask that you first open an issue or discussion.

Before submitting a PR, please test your changes in your own fork. Please do not open a pull request immediately and add to it frequently during development &mdash; this will saturate the `modflowpy` organization's CI.

If `develop` changes while your work is still in progress, please rebase and fix any conflicts, then force push your branch to update the pull request.

## Commit messages

Commit messages must conform to the [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This makes the commit history easier to follow and allows an automatically generated changelog.

### Commit Message Format

Each commit message consists of a **header**, a **body** and a **footer**. The **header** is mandatory, while **body** and **footer** are optional.

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

Note the header's format, which includes a **type**, a **scope** and a **subject**. Header **type** and **subject** are mandatory while header **scope** is optional.

No line of the commit message may be longer 100 characters. This makes messages easier to read on GitHub as well as in various `git` tools.

If a commit closes an issue, the footer should contain a [closing reference](https://help.github.com/articles/closing-issues-via-commit-messages/).

#### Type

Must be one of the following:

* **ci**: Changes to our CI configuration files and scripts (example scopes: Travis)
* **docs**: Documentation only changes
* **feat**: A new feature
* **fix**: A bug fix
* **perf**: A code change that improves performance
* **refactor**: A code change that neither fixes a bug nor adds a feature
* **style**: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
* **test**: Adding missing tests or correcting existing tests
* **revert**: Reverts a previous commit

#### Subject

The subject contains a succinct description of the change:

* use the imperative, present tense: "change" not "changed" nor "changes"
* don't capitalize the first letter
* do not include a dot (.) at the end

#### Body

Just as in the **subject**, use the imperative, present tense: "change" not "changed" nor "changes".
The body should include the motivation for the change and contrast this with previous behavior.

#### Footer

The footer should contain any information about **Breaking Changes** and is also the place to reference GitHub issues that this commit **Closes**.

**Breaking Changes** should start with the word `BREAKING CHANGE:` with a space or two newlines. The rest of the commit message is then used for this.