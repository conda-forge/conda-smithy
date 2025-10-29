# Linter messages

Categories:
- [`CBC`: Variants configuration (`conda_build_config.yaml`)](#CBC)
- [`CF`: Recipe issues specific to conda-forge](#CF)
- [`FC`: Feedstock configuration (`conda-forge.yml`)](#FC)
- [`R`: All recipe versions](#R)
- [`R0`: Recipe v0 (`meta.yaml`)](#R0)
- [`R1`: Recipe v1 (`recipe.yaml`)](#R1)
<a id='CBC'></a>
## `CBC`: Variants configuration (`conda_build_config.yaml`)

<a id='CBC-000'></a>
### `CBC-000`: `CBCMacOSDeploymentTargetConflict`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
Conflicting specification for minimum macOS deployment target!
If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, please change the name of that key to `c_stdlib_version`!
Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`.
```

</details>

<a id='CBC-001'></a>
### `CBC-001`: `CBCMacOSDeploymentTargetRename`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
In your conda_build_config.yaml, please change the name of `MACOSX_DEPLOYMENT_TARGET`, to `c_stdlib_version`!
```

</details>

<a id='CBC-002'></a>
### `CBC-002`: `CBCMacOSDeploymentTargetBelow`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
You are setting `c_stdlib_version` below the current global baseline in conda-forge (10.13). If this is your intention, you also need to override `MACOSX_DEPLOYMENT_TARGET` (with the same value) locally.
```

</details>

<a id='CBC-003'></a>
### `CBC-003`: `CBCMacOSDeploymentTargetBelowStdlib`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
You are setting `MACOSX_SDK_VERSION` below `c_stdlib_version`, in conda_build_config.yaml which is not possible! Please ensure `MACOSX_SDK_VERSION` is at least `c_stdlib_version` (you can leave it out if it is equal).
If you are not setting `c_stdlib_version` yourself, this means you are requesting a version below the current global baseline in conda-forge (10.13). If this is the intention, you also need to override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally.
```

</details>

<a id='CF'></a>
## `CF`: Recipe issues specific to conda-forge

<a id='CF-001'></a>
### `CF-001`: `CFMaintainerExists`


Maintainers listed in `extra.recipe-maintainers` must be valid Github usernames
or `@conda-forge/*` teams.

<details>

<summary>Lint message</summary>

```text
Recipe maintainer {team_or}"{maintainer}" does not exist
```

</details>

<a id='CF-002'></a>
### `CF-002`: `CFPackageToAvoid`


Some package names may not be used in recipes directly, or under some circumstances.

The full list of package names and their explanations can be found in
[`conda-forge-pinning-feedstock`](https://github.com/conda-forge/conda-forge-pinning-feedstock/blob/main/recipe/linter_hints/hints.toml).

<details>

<summary>Hint message</summary>

```text
{package_hint}
```

</details>

<a id='CF-004'></a>
### `CF-004`: `CFNoCiSupport`


No `.ci_support/*.yaml` files could be found, which means that build matrix is empty
and no packages will be built.

This is usually caused by a misconfiguration of your recipe file (e.g. `build.skip` is always
`true`, disabling all builds).

<details>

<summary>Lint message</summary>

```text
The feedstock has no `.ci_support` files and thus will not build any packages.
```

</details>

<a id='FC'></a>
## `FC`: Feedstock configuration (`conda-forge.yml`)

<a id='FC-001'></a>
### `FC-001`: `FCNoDuplicateKeys`


`conda-forge.yml` must not contain duplicate keys.

<details>

<summary>Lint message</summary>

```text
The ``conda-forge.yml`` file is not allowed to have duplicate keys.
```

</details>

<a id='R'></a>
## `R`: All recipe versions

<a id='R-000'></a>
### `R-000`: `RecipeUnexpectedSection`


Recipe files must not contain unknown top-level keys.

<details>

<summary>Lint message</summary>

```text
The top level meta key {section} is unexpected
```

</details>

<a id='R-001'></a>
### `R-001`: `RecipeSectionOrder`


The top-level sections of a recipe file must always follow the same order.

<details>

<summary>Lint message</summary>

```text
The top level meta keys are in an unexpected order. Expecting {order}.
```

</details>

<a id='R-002'></a>
### `R-002`: `RecipeMissingAboutItem`


The `about` section requires three fields: homepage (`home` in v1), license, and summary.

<details>

<summary>Lint message</summary>

```text
The {item} item is expected in the about section.
```

</details>

<a id='R-003'></a>
### `R-003`: `RecipeNoMaintainers`


All recipes must list at least one maintainer under `extra/recipe-maintainers`.

<details>

<summary>Lint message</summary>

```text
The recipe could do with some maintainers listed in the `extra/recipe-maintainers` section.
```

</details>

<a id='R-004'></a>
### `R-004`: `RecipeMaintainersMustBeList`


The `extra/recipe-maintainers` only accepts a list of strings as a value.

<details>

<summary>Lint message</summary>

```text
Recipe maintainers should be a json list.
```

</details>

<a id='R-005'></a>
### `R-005`: `RecipeRequiredTests`


All recipes must have a non-empty `test` section.

<details>

<summary>Lint message</summary>

```text
The recipe must have some tests.
```

</details>

<a id='R-006'></a>
### `R-006`: `RecipeRecommendedTests`


All recipes must have a non-empty `test` section.

<details>

<summary>Hint message</summary>

```text
It looks like the '{output}' output doesn't have any tests.
```

</details>

<a id='R-007'></a>
### `R-007`: `RecipeUnknownLicense`


All recipes must have a license identifier, but it can't be "unknown".

<details>

<summary>Lint message</summary>

```text
The recipe license cannot be unknown.
```

</details>

<a id='R-008'></a>
### `R-008`: `RecipeBuildNumberMissing`


All recipes must define a `build.number` value.

<details>

<summary>Lint message</summary>

```text
The recipe must have a `build/number` section.
```

</details>

<a id='R-009'></a>
### `R-009`: `RecipeRequirementsOrder`


The different subcategories of the `requirements` section must follow
a strict order: `build`, `host`, `run`, `run_constrained`.

<details>

<summary>Lint message</summary>

```text
The `requirements/` sections should be defined in the following order: {expected}; instead saw: {seen}.
```

</details>

<a id='R-010'></a>
### `R-010`: `RecipeLicenseLicense`


Licenses should omit the term 'License' in its name.

<details>

<summary>Lint message</summary>

```text
The recipe `license` should not include the word "License".
```

</details>

<a id='R-011'></a>
### `R-011`: `RecipeTooManyEmptyLines`


Recipe files should end with a single empty line, not more.

<details>

<summary>Lint message</summary>

```text
There are {n_lines} too many lines.  There should be one empty line at the end of the file.
```

</details>

<a id='R-012'></a>
### `R-012`: `RecipeTooFewEmptyLines`


Recipe files should end with a single empty line.

<details>

<summary>Lint message</summary>

```text
There are too few lines.  There should be one empty line at the end of the file.
```

</details>

<a id='R-013'></a>
### `R-013`: `RecipeLicenseFamily`


The field `license_file` must be always present.

<details>

<summary>Lint message</summary>

```text
license_file entry is missing, but is required.
```

</details>

<a id='R-014'></a>
### `R-014`: `RecipeName`


The recipe `name` can only contain certain characters:

- lowercase ASCII letters (`a-z`)
- digits (`0-9`)
- underscores, hyphens and dots (`_`, `-`, `.`)

<details>

<summary>Lint message</summary>

```text
Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed
```

</details>

<a id='R-015'></a>
### `R-015`: `RecipeMissingVersion`


The package `version` field is required.

<details>

<summary>Lint message</summary>

```text
Package version is missing.
```

</details>

<a id='R-016'></a>
### `R-016`: `RecipeInvalidVersion`


The package `version` field must be a valid version string.

<details>

<summary>Lint message</summary>

```text
Package version {version} doesn't match conda spec: {error}
```

</details>

<a id='R-017'></a>
### `R-017`: `RecipePinnedNumpy`


See <https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy>

<details>

<summary>Lint message</summary>

```text
Using pinned numpy packages is a deprecated pattern.  Consider using the method outlined [here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy).
```

</details>

<a id='R-018'></a>
### `R-018`: `RecipeUnexpectedSubsection`


This check ensures that the passed recipe conforms to the expected recipe v0 schema.

See schema in [`conda_build.metadata.FIELDS`](
https://github.com/conda/conda-build/blob/25.9.0/conda_build/metadata.py#L619)

<details>

<summary>Lint message</summary>

```text
The {section} section contained an unexpected subsection name. {subsection} is not a valid subsection name.
```

</details>

<a id='R-019'></a>
### `R-019`: `RecipeSourceHash`


All recipe source URLs must have a hash checksum for integrity checks.

<details>

<summary>Lint message</summary>

```text
When defining a source/url please add a sha256, sha1 or md5 checksum (sha256 preferably).
```

</details>

<a id='R-020'></a>
### `R-020`: `RecipeNoarchValue`


The `build.noarch` field can only take `python` or `generic` as a value.

<details>

<summary>Lint message</summary>

```text
Invalid `noarch` value `{given}`. Should be one of `{valid}`.
```

</details>

<a id='R-021'></a>
### `R-021`: `RecipeRequirementJoinVersionOperator`


conda recipes should use the three-field matchspec syntax to express requirements:
`name [version [build]]`. This means having no spaces between operator and version
literals.

<details>

<summary>Lint message</summary>

```text
``requirements: {section}: {requirement}`` should not contain a space between relational operator and the version, i.e. ``{name} {pin}``
```

</details>

<a id='R-022'></a>
### `R-022`: `RecipeRequirementSeparateNameVersion`


conda recipes should use the three-field matchspec syntax to express requirements:
`name [version [build]]`. This means having a space between name and version.

<details>

<summary>Lint message</summary>

```text
``requirements: {section}: {requirement}`` must contain a space between the name and the pin, i.e. ``{name} {pin}``
```

</details>

<a id='R-023'></a>
### `R-023`: `RecipeLanguageHostRun`


Packages may depend on certain languages (e.g. Python, R) that require depending
on the language runtime both in `host` and `run`.

<details>

<summary>Lint message</summary>

```text
If {language} is a host requirement, it should be a run requirement.
```

</details>

<a id='R-024'></a>
### `R-024`: `RecipeLanguageHostRunUnpinned`


Packages may depend on certain languages (e.g. Python, R) that require depending
on the language runtime both in `host` and `run`. They should not pin it to a
particular version when the package is not `noarch`.

<details>

<summary>Lint message</summary>

```text
Non noarch packages should have {language} requirement without any version constraints.
```

</details>

<a id='R-025'></a>
### `R-025`: `RecipeJinjaExpression`


Jinja expressions should add a space between the double curly braces.

<details>

<summary>Hint message</summary>

```text
Jinja2 variable references are suggested to take a ``{dollar}{{{{<one space><variable name><one space>}}}}`` form. See lines {lines}.
```

</details>

<a id='R-026'></a>
### `R-026`: `RecipePythonLowerBound`


Noarch Python recipes should always pin the lower bound on their `python` requirement.

<details>

<summary>Lint message</summary>

```text
noarch: python recipes are required to have a lower bound on the python version. Typically this means putting `python >={{{{ python_min }}}}` in the `run` section of your recipe. You may also want to check the upstream source for the package's Python compatibility.
```

</details>

<a id='R-027'></a>
### `R-027`: `RecipePinSubpackagePinCompatible`


The Jinja functions `pin_subpackage` and `pin_compatible` may be confused
because both would add version constraints to a package name. However, they
have different purposes.

- `pin_subpackage()` must be used when the package to be pinned is a known output
  in the current recipe.
- `pin_compatible()` must be used when the package to be pinned is _not_ an output
  of the current recipe.

<details>

<summary>Lint message</summary>

```text
{should_use} should be used instead of {in_use} for `{pin}` because it is {what} known outputs of this recipe: {subpackages}.
```

</details>

<a id='R-028'></a>
### `R-028`: `RecipeCompiledWheelsNotAllowed`


Python wheels are often discouraged as package sources. This is especially the case
for compiled wheels, which are forbidden.

<details>

<summary>Lint message</summary>

```text
Detected compiled wheel(s) in source: {urls}. This is disallowed. All packages should be built from source except in rare and exceptional cases.
```

</details>

<a id='R-029'></a>
### `R-029`: `RecipePureWheelsNotAllowed`


Python wheels are often discouraged as package sources. This is also the case
for pure Python wheels when building non-noarch packages.

<details>

<summary>Lint message</summary>

```text
Detected pure Python wheel(s) in source: {urls}. This is discouraged. Please consider using a source distribution (sdist) instead.
```

</details>

<a id='R-030'></a>
### `R-030`: `RecipePureWheelsNotAllowedNoarch`


Python wheels are often discouraged as package sources. However, pure Python
wheels may be used as a source for noarch Python packages, although sdists are preferred.

<details>

<summary>Hint message</summary>

```text
Detected pure Python wheel(s) in source: {urls}. This is generally ok for pure Python wheels and noarch=python packages but it's preferred to use a source distribution (sdist) if possible.
```

</details>

<a id='R-031'></a>
### `R-031`: `RecipeRustLicenses`


<https://conda-forge.org/docs/maintainer/adding_pkgs/#rust>

<details>

<summary>Lint message</summary>

```text
Rust packages must include the licenses of the Rust dependencies. For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust
```

</details>

<a id='R-032'></a>
### `R-032`: `RecipeGoLicenses`


<https://conda-forge.org/docs/maintainer/adding_pkgs/#go>

<details>

<summary>Lint message</summary>

```text
Go packages must include the licenses of the Go dependencies. For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go
```

</details>

<a id='R-033'></a>
### `R-033`: `RecipeStdlibJinja`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
This recipe is using a compiler, which now requires adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}` as well. Note that this rule applies to each output of the recipe using a compiler. For further details, please see https://github.com/conda-forge/conda-forge.github.io/issues/2102.
```

</details>

<a id='R-034'></a>
### `R-034`: `RecipeStdlibSysroot`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
You're setting a requirement on sysroot_linux-<arch> directly; this should now be done by adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}`, and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the respective platform as necessary. For further details, please see https://github.com/conda-forge/conda-forge.github.io/issues/2102.
```

</details>

<a id='R-035'></a>
### `R-035`: `RecipeStdlibOsx`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
You're setting a constraint on the `__osx` virtual package directly; this should now be done by adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}`, and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the respective platform as necessary. For further details, please see https://github.com/conda-forge/conda-forge.github.io/issues/2102.
```

</details>

<a id='R-036'></a>
### `R-036`: `RecipeNotParsableLint`


The conda recipe should be parsable by at least one backend.
If none can parse it, this constitutes an error that needs to be remediated.

<details>

<summary>Lint message</summary>

```text
The recipe is not parsable by any of the known recipe parsers ({parsers}). Please check the logs for more information and ensure your recipe can be parsed.
```

</details>

<a id='R-037'></a>
### `R-037`: `RecipeNotParsableHint`


The conda recipe should be parsable by at least one backend.
Sometimes, only some backends fail, which is not critical, but should be looked into.

_Message generated dynamically. Template not available._

<a id='R-038'></a>
### `R-038`: `RecipePythonIsAbi3Bool`


https://github.com/conda-forge/conda-forge.github.io/issues/2102

<details>

<summary>Lint message</summary>

```text
The `is_abi3` variant variable is now a boolean value instead of a string (i.e., 'true' or 'false'). Please change syntax like `is_abi3 == 'true' to `is_abi3`.
```

</details>

<a id='R0'></a>
## `R0`: Recipe v0 (`meta.yaml`)

<a id='R0-001'></a>
### `R0-001`: `RecipeFormattedSelectors`


Recipe format v0 (`meta.yaml`) supports the notion of line selectors
as trailing comments:

```yaml
build:
  skip: true  # [not win]
```

These must be formatted with two spaces before the `#` symbol, followed
by one space before the opening square bracket `[`, followed by no spaces.
The closing bracket must not be surrounded by spaces either.

<details>

<summary>Lint message</summary>

```text
Selectors are suggested to take a ``<two spaces>#<one space>[<expression>]`` form. See lines {lines}
```

</details>

<a id='R0-002'></a>
### `R0-002`: `RecipeOldPythonSelectorsLint`


Recipe v0 selectors used to include one Python version selector
per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
This was deprecated in favor of the `py` integer, which is preferred.

<details>

<summary>Lint message</summary>

```text
Old-style Python selectors (py27, py35, etc) are only available for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. See lines {lines}
```

</details>

<a id='R0-003'></a>
### `R0-003`: `RecipeOldPythonSelectorsHint`


Recipe v0 selectors (see [`R0-002`](#r0-002)) used to include one Python
version selector per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
This was deprecated in favor of the `py` integer, which is preferred.

<details>

<summary>Hint message</summary>

```text
Old-style Python selectors (py27, py34, py35, py36) are deprecated. Instead, consider using the int ``py``. For example: ``# [py>=36]``. See lines {lines}
```

</details>

<a id='R0-004'></a>
### `R0-004`: `RecipeNoarchSelectorsV0`


Noarch packages are not generally compatible with v0 selectors

<details>

<summary>Lint message</summary>

```text
`noarch` packages can't have {skips}selectors. If the selectors are necessary, please remove `noarch: {noarch}`, or selector on line {line_number}:
{line}
```

</details>

<a id='R0-005'></a>
### `R0-005`: `RecipeJinjaDefinitions`


In v0 recipes, Jinja definitions must follow a particular style.

<details>

<summary>Lint message</summary>

```text
Jinja2 variable definitions are suggested to take a ``{{%<one space>set<one space><variable name><one space>=<one space><expression><one space>%}}`` form. See lines {lines}
```

</details>

<a id='R0-006'></a>
### `R0-006`: `RecipeLegacyToolchain`


The `toolchain` package is deprecated. Use compilers as outlined in
<https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers>.

<details>

<summary>Lint message</summary>

```text
Using toolchain directly in this manner is deprecated.  Consider using the compilers outlined [here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers).
```

</details>

<a id='R1'></a>
## `R1`: Recipe v1 (`recipe.yaml`)

<a id='R1-001'></a>
### `R1-001`: `RecipeNoCommentSelectors`


Recipe v0 selectors (see [`R0-002`](#r0-002)) are not supported in v1 recipes.

<details>

<summary>Lint message</summary>

```text
Selectors in comment form no longer work in v1 recipes. Instead, if / then / else maps must be used. See lines {lines}.
```

</details>

<a id='R1-002'></a>
### `R1-002`: `RecipeNoarchSelectorsV1`


Noarch packages are not generally compatible with v1 conditional blocks.

<details>

<summary>Lint message</summary>

```text
`noarch` packages can't have {skips}selectors. If the selectors are necessary, please remove `noarch: {noarch}`.
```

</details>
