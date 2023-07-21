# Generating TOCs

The [`doctoc`](https://www.npmjs.com/package/doctoc) tool generates table of contents sections for markdown files.

## Installing Node.js, `npm` and `doctoc``

`doctoc` is distributed with the [Node Package Manager](https://docs.npmjs.com/cli/v7/configuring-npm/install). [Node](https://nodejs.org/en) is a JavaScript runtime environment.

On Ubuntu, Node can be installed with:

```shell
sudo apt update
sudo apt install nodejs
```

On Windows, with [Chocolatey](https://community.chocolatey.org/packages/nodejs):

```shell
choco install nodejs
```

Installers and binaries for Windows and macOS are [available for download](https://nodejs.org/en/download).

Once Node is installed, install `doctoc` with:

```shell
npm install -g doctoc
```

## Using `doctoc`

Then TOCs can be generated with `doctoc <file>`, e.g.:

```shell
doctoc DEVELOPER.md
```

This will insert HTML comments surrounding an automatically edited region, in which `doctoc` will create an appropriately indented TOC tree. Subsequent runs are idempotent, scanning for headers and only updating the TOC if the file header structure has changed.

To run `doctoc` for all markdown files in a particular directory (recursive), use `doctoc some/path`.

By default `doctoc` inserts a self-descriptive comment

> **Table of Contents** *generated with DocToc*

This can be removed (and other content within the TOC region edited) &mdash; `doctoc` will not overwrite it, only the table.
