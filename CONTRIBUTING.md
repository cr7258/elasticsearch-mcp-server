# Contributing to Elasticsearch/OpenSearch MCP Server

Thank you for your interest in contributing to the Elasticsearch/OpenSearch MCP Server! All kinds of contributions are welcome.

## Bug reports

If you think you've found a bug in the Elasticsearch/OpenSearch MCP Server, we welcome your report. It's very helpful if you can provide steps to reproduce the bug, as it makes it easier to identify and fix the issue.

## Feature requests

If you find yourself wishing for a feature that doesn't exist in the Elasticsearch/OpenSearch MCP Server, you are probably not alone. Don't be hesitate to open an issue which describes the feature you would like to see, why you need it, and how it should work.

## Pull requests

If you have a fix or a new feature, we welcome your pull requests. You can follow the following steps:

1. Fork your own copy of the repository to your GitHub account by clicking on
   `Fork` button on [elasticsearch-mcp-server's GitHub repository](https://github.com/cr7258/elasticsearch-mcp-server).
2. Clone the forked repository on your local setup.

    ```bash
    git clone https://github.com/$user/elasticsearch-mcp-server
    ```

   Add a remote upstream to track upstream `elasticsearch-mcp-server` repository.

    ```bash
    git remote add upstream https://github.com/cr7258/elasticsearch-mcp-server
    ```

3. Create a topic branch.

    ```bash
    git checkout -b <branch-name>
    ```

4. Make changes and commit it locally.

    ```bash
    git add <modifiedFile>
    git commit
    ```

Commit message could help reviewers better understand what is the purpose of submitted PR. It could help accelerate the code review procedure as well. We encourage contributors to use **EXPLICIT** commit message rather than ambiguous message. In general, we advocate the following commit message type:
- Features: commit message start with `feat`, For example: "feat: add user authentication module"
- Bug Fixes: commit message start with `fix`, For example: "fix: resolve null pointer exception in user service"
- Documentation, commit message start with `doc`, For example: "doc: update API documentation for user endpoints"
- Performance: commit message start with `perf`, For example: "perf: improve the performance of user service"
- Refactor: commit message start with `refactor`, For example: "refactor: refactor user service to improve code readability"
- Test: commit message start with `test`, For example: "test: add unit test for user service"
- Chore: commit message start with `chore`, For example: "chore: update dependencies in pom.xml"
- Style: commit message start with `style`, For example: "style: format the code in user service"
- Revert: commit message start with `revert`, For example: "revert: revert the changes in user service"

5. Push local branch to your forked repository.

    ```bash
    git push
    ```

6. Create a Pull request on GitHub.
   Visit your fork at `https://github.com/$user/elasticsearch-mcp-server` and click
   `Compare & Pull Request` button next to your `<branch-name>`.


## Keeping branch in sync with upstream

Click `Sync fork` button on your forked repository to keep your forked repository in sync with the upstream repository. 

If you have already created a branch and want to keep it in sync with the upstream repository, follow the below steps:

```bash
git checkout <branch-name>
git fetch upstream
git rebase upstream/main
```