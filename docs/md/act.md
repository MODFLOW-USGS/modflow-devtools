# Local CI testing

The [`act`](https://github.com/nektos/act) tool uses Docker to run containerized CI workflows in a simulated GitHub Actions environment. [Docker Desktop](https://www.docker.com/products/docker-desktop/) is required for Mac or Windows and [Docker Engine](https://docs.docker.com/engine/) on Linux.

With Docker installed and running, run `act -l` from the project root to see available CI workflows. To run all workflows and jobs, just run `act`. To run a particular workflow use `-W`:

```shell
act -W .github/workflows/commit.yml
```

To run a particular job within a workflow, add the `-j` option:

```shell
act -W .github/workflows/commit.yml -j build
```

**Note:** GitHub API rate limits are easy to exceed, especially with job matrices. Authenticated GitHub users have a much higher rate limit: use `-s GITHUB_TOKEN=<your token>` when invoking `act` to provide a personal access token. Note that this will log your token in shell history &mdash; leave the value blank for a prompt to enter it more securely.

The `-n` flag can be used to execute a dry run, which doesn't run anything, just evaluates workflow, job and step definitions. See the [docs](https://github.com/nektos/act#example-commands) for more.

**Note:** `act` can only run Linux-based container definitions, so Mac or Windows workflows or matrix OS entries will be skipped.