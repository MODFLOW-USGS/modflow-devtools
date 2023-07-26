### Version 0.2.0

#### New features

* [feat(set_env)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/53b31cce34d221bade4c842efe3b5ed3034b2742): Add set_env contextmanager utility (#87). Committed by w-bonelli on 2023-07-26.

### Version 0.1.8

#### New features

* [feat(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/3bf76d587a04954cc68a07d38e48876d42f06b58): Discover external model repo dirs with .git suffix (#80). Committed by w-bonelli on 2023-04-21.

#### Bug fixes

* [fix(multiple)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/2307add30eb3134a786f7c722656b4d99a0fe91a): Fix some CI and fixture issues (#81). Committed by w-bonelli on 2023-04-21.

### Version 0.1.7

#### Refactoring

* [refactor(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/2bbe35f3a4b63d9c6d558d7669c986a6fb7056de): Add entries to default exe name/path mapping (#75). Committed by w-bonelli on 2023-03-01.
* [refactor(versioning)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/5fbc6b98e34afe9e43cc1d8c1b26f87e64f00699): Don't track version explicitly in readme (#76). Committed by w-bonelli on 2023-04-06.

### Version 0.1.6

#### Refactoring

* [refactor(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/a9570097d640a4c071dd1bee2d09ea99cac8ffa1): Overwrite keepable temp dirs by default (#67). Committed by w-bonelli on 2023-01-20.
* [refactor(download)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/1ced91dc3a0619016728358d69e7563e175e6fac): Refactor GH API utils, add tests, update docs (#68). Committed by w-bonelli on 2023-02-03.

### Version 0.1.5

#### Refactoring

* [refactor(metadata)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/2edeacfd8cb10081c22d1ab0799aba1fa7522c0d): Use pyproject.toml, retire setup.cfg (#63). Committed by w-bonelli on 2023-01-19.

### Version 0.1.4

#### Bug fixes

* [fix(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/8b9aeec73885c3aa2f8bbcfa84c99824fe703cbb): Fix package detection/selection (#60). Committed by w-bonelli on 2023-01-18.

#### Refactoring

* [refactor(has_pkg)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/861fa80f236bb9fcfcf4cfb1e9a391ad33076060): Use import.metadata instead of pkg_resources (#54). Committed by Mike Taves on 2023-01-09.

### Version 0.1.3

#### Bug fixes

* [fix(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/32e227bd2a6db39d3dada29ceb4ea6279f215f94): Fix test_model_mf6 fixture node id (#49). Committed by w-bonelli on 2023-01-07.

#### Refactoring

* [refactor(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/9987209620bf6b0422079d605c996c868116d725): Update defaults for model-finding fixtures (#48). Committed by w-bonelli on 2023-01-07.

### Version 0.1.2

#### Bug fixes

* [fix(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/aeccdb3d66f5f927ae9b7b4c66bf6d4d0610e379): Fix model filtering by package (#44). Committed by w-bonelli on 2023-01-04.

### Version 0.1.1

#### Bug fixes

* [fix(release)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/b8255caaeb3a7c7d140aecbf590237e4b0d8ec1d): Fix conf.py version fmt, fix update_version.py. Committed by w-bonelli on 2022-12-29.
* [fix(release)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/373d4f4fab212ea0a25b3b805a8fd363cbf50f7b): Fix changelog commit links (#38). Committed by w-bonelli on 2022-12-29.
* [fix(license)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/18417f0ca5daddde6379ec9cd28a52f0567b4f63): Remove extra LICENSE file, fix link in LICENSE.md (#39). Committed by w-bonelli on 2022-12-30.

#### Refactoring

* [refactor(utilities)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/5a1c49bef57eacb49114976f336823ab9fb8964b): Restore get_model_paths function name (#41). Committed by w-bonelli on 2022-12-30.

### Version 0.1.0

#### Refactoring

* [refactor(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/23593df7fb427d6de1d33f9aa408697d2536e473): Fix/refactor model-loading fixtures (#33). Committed by w-bonelli on 2022-12-29.

### Version 0.0.8

#### Bug fixes

* [fix(release)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/b62547bd607f9a0d3a78be61d16976bf406151f5): Exclude intermediate changelog (#28). Committed by w-bonelli on 2022-12-28.
* [fix(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/a2d4b9210db532f12cf87ae5d26582d1ed446463): Fix example_scenario fixture loading (#30). Committed by w-bonelli on 2022-12-29.

### Version 0.0.7

#### Refactoring

* [refactor(executables)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/58c3642d0e6d20d5e34783b5b61e8238058e102f): Simplify exes container, allow dict access (#24). Committed by w-bonelli on 2022-12-28.
* [refactor](https://github.com/MODFLOW-USGS/modflow-devtools/commit/50c83a9eaed532722549a2d9da1eb79ed8cf01be): Drop Python 3.7, add Python 3.11 (#25). Committed by w-bonelli on 2022-12-28.

### Version 0.0.6

#### New features

* [feat(build)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/3108c380f29424bcdd1643479f66e849f7f762eb): Restore meson_build function (#15). Committed by w-bonelli on 2022-11-14.

#### Bug fixes

* [fix](https://github.com/MODFLOW-USGS/modflow-devtools/commit/933c79741b0e6a6db7c827414ebf635e62445772): Changes to support running of existing tests (#6). Committed by mjreno on 2022-07-20.
* [fix(ci)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/0bb31907200be32bf2a045d54131f0a1dbd0ae2f): Don't build/test examples on python 3.7 (xmipy requires 3.8+) (#10). Committed by w-bonelli on 2022-11-08.
* [fix(tests)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/3c63aaae581d335b1111b8dd2b929004b3281980): Mark test_download_and_unzip flaky (#11). Committed by w-bonelli on 2022-11-08.
* [fix(fixtures)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/1e5fabdeb6d431f960316b049d68c4919650888c): Fix model-loading fixtures and utilities (#12). Committed by w-bonelli on 2022-11-11.
* [fix(misc)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/80b8d1e1549676debda09383f75db50f5f11417a): Fix multiple issues (#16). Committed by w-bonelli on 2022-11-19.
* [fix(auth)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/89db96ff5fb6e080c189f3a3e348ddf2ded21212): Fix GH API auth token in download_and_unzip (#17). Committed by w-bonelli on 2022-11-19.
* [fix(download)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/58dff9f6c1245b22e3dc10411862d6eacea42e94): Use 'wb' instead of 'ab' mode when writing downloaded files, add retries (#20). Committed by w-bonelli on 2022-12-01.

#### Refactoring

* [refactor](https://github.com/MODFLOW-USGS/modflow-devtools/commit/5aff3427351a0bbe38927d81dad42dd5374b67be): Updates to support modflow6 autotest and remove data path. Committed by mjreno on 2022-08-05.
* [refactor](https://github.com/MODFLOW-USGS/modflow-devtools/commit/e9e14f959e2a2ea016114c2dbfc35555b81459aa): Updates to support modflow6 autotest and remove data path. Committed by mjreno on 2022-08-05.
* [refactor(ci)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/eefb659bb04df6aa18432165850a512285812d15): Create release and publish to PyPI when tags pushed (#14). Committed by w-bonelli on 2022-11-14.
* [refactor(misc)](https://github.com/MODFLOW-USGS/modflow-devtools/commit/1672733df1c17b802f1ade7d28db7bdb90496714): Refactor gh api & other http utilities (#18). Committed by w-bonelli on 2022-11-26.
* [refactor](https://github.com/MODFLOW-USGS/modflow-devtools/commit/bb8fa593cd21f2c0e8e9f3a6c2125fc22d5d9858): Remove mf6 file parsing fns (moved to modflow-devtools) (#19). Committed by w-bonelli on 2022-11-28.

