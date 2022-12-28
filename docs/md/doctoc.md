# Generating TOCs

The [`doctoc`](https://www.npmjs.com/package/doctoc) tool can be used to automatically generate table of contents sections for markdown files. `doctoc` is distributed with the [Node Package Manager](https://docs.npmjs.com/cli/v7/configuring-npm/install). With Node installed use `npm install -g doctoc` to install `doctoc` globally. Then just run `doctoc <file>`, e.g.:

```shell
doctoc DEVELOPER.md
```

This will insert HTML comments surrounding an automatically edited region, scanning for headers and creating an appropriately indented TOC tree.  Subsequent runs are idempotent, updating if the file has changed or leaving it untouched if not.

To run `doctoc` for all markdown files in a particular directory (recursive), use `doctoc some/path`.