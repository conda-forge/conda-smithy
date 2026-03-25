# Linter messages

Categories:
- [`CBC`: Only `conda_build_config.yaml`](#CBC)
- [`CF`: conda-forge specific rules](#CF)
- [`FC`: Feedstock configuration in `conda-forge.yml`.](#FC)
- [`R`: All recipe versions](#R)
- [`R0`: Only `meta.yaml`](#R0)
- [`R1`: Only `recipe.yaml`](#R1)
- [`RC`: All recipe variants files](#RC)

<a id='CBC'></a>
## `CBC`: Only `conda_build_config.yaml`

<a id='CBC-000'></a>
### ~~`CBC-000`: `CBCMacOSDeploymentTargetConflict`~~

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.
- **Deprecated in: conda-smithy 3.56.0**

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
Conflicting specification for minimum macOS deployment target!
If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, please change the name of that key to `c_stdlib_version`!
Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`.
```

</details>

_No samples available_

<a id='CF'></a>
## `CF`: conda-forge specific rules

<a id='CF-001'></a>
### `CF-001`: `CFMaintainerExists`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Maintainers listed in `extra.recipe-maintainers` must be valid Github usernames
or `@conda-forge/*` teams.

#### Samples

<details>

<summary>Base template</summary>

```text
Recipe maintainer {team_or}"{maintainer}" does not exist
```

</details>

_No samples available_

<a id='CF-002'></a>
### `CF-002`: `CFPackageToAvoid`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Some package names may not be used in recipes directly, or under some circumstances.

The full list of package names and their explanations can be found in
[`conda-forge-pinning-feedstock`](https://github.com/conda-forge/conda-forge-pinning-feedstock/blob/main/recipe/linter_hints/hints.toml).

#### Samples

<details>

<summary>Base template</summary>

```text
{package_hint}
```

</details>

_No samples available_

<a id='CF-004'></a>
### `CF-004`: `CFNoCiSupport`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

No `.ci_support/*.yaml` files could be found, which means that build matrix is empty
and no packages will be built.

This is usually caused by a misconfiguration of your recipe file (e.g. `build.skip` is always
`true`, disabling all builds).

#### Samples

<details>

<summary>Base template</summary>

```text
The feedstock has no `.ci_support` files and thus will not build any packages.
```

</details>

_No samples available_

<a id='FC'></a>
## `FC`: Feedstock configuration in `conda-forge.yml`.

<a id='FC-001'></a>
### `FC-001`: `FCNoDuplicateKeys`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

`conda-forge.yml` must not contain duplicate keys.

#### Samples

<details>

<summary>Base template</summary>

```text
The ``conda-forge.yml`` file is not allowed to have duplicate keys.
```

</details>

_No samples available_

<a id='R'></a>
## `R`: All recipe versions

<a id='R-000'></a>
### `R-000`: `RecipeUnexpectedSection`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Recipe files must not contain unknown top-level keys.

#### Samples

<details>

<summary>Base template</summary>

```text
The top level meta key {section} is unexpected
```

</details>

_No samples available_

<a id='R-001'></a>
### `R-001`: `RecipeSectionOrder`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The top-level sections of a recipe file must always follow the same order.

#### Samples

<details>

<summary>Base template</summary>

```text
The top level meta keys are in an unexpected order. Expecting {order}.
```

</details>

_No samples available_

<a id='R-002'></a>
### `R-002`: `RecipeMissingAboutItem`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The `about` section requires three fields: homepage (`home` in v1), license, and summary.

#### Samples

<details>

<summary>Base template</summary>

```text
The {item} item is expected in the about section.
```

</details>

_No samples available_

<a id='R-003'></a>
### `R-003`: `RecipeNoMaintainers`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

All recipes must list at least one maintainer under `extra/recipe-maintainers`.

#### Samples

<details>

<summary>Base template</summary>

```text
The recipe could do with some maintainers listed in the `extra/recipe-maintainers` section.
```

</details>

_No samples available_

<a id='R-004'></a>
### `R-004`: `RecipeMaintainersMustBeList`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The `extra/recipe-maintainers` only accepts a list of strings as a value.

#### Samples

<details>

<summary>Base template</summary>

```text
Recipe maintainers should be a json list.
```

</details>

_No samples available_

<a id='R-005'></a>
### `R-005`: `RecipeRequiredTests`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

All recipes must have a non-empty `test` section.

#### Samples

<details>

<summary>Base template</summary>

```text
The recipe must have some tests.
```

</details>

_No samples available_

<a id='R-006'></a>
### `R-006`: `RecipeRecommendedTests`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

All recipes must have a non-empty `test` section.

#### Samples

<details>

<summary>Base template</summary>

```text
It looks like the '{output}' output doesn't have any tests.
```

</details>

_No samples available_

<a id='R-007'></a>
### `R-007`: `RecipeUnknownLicense`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

All recipes must have a license identifier, but it can't be "unknown".

#### Samples

<details>

<summary>Base template</summary>

```text
The recipe license cannot be unknown.
```

</details>

_No samples available_

<a id='R-008'></a>
### `R-008`: `RecipeBuildNumberMissing`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

All recipes must define a `build.number` value.

#### Samples

<details>

<summary>Base template</summary>

```text
The recipe must have a `build/number` section.
```

</details>

_No samples available_

<a id='R-009'></a>
### `R-009`: `RecipeRequirementsOrder`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The different subcategories of the `requirements` section must follow
a strict order: `build`, `host`, `run`, `run_constrained`.

#### Samples

<details>

<summary>Base template</summary>

```text
The `requirements/` sections should be defined in the following order: {expected}; instead saw: {seen}.
```

</details>

_No samples available_

<a id='R-010'></a>
### `R-010`: `RecipeLicenseLicense`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Licenses should omit the term 'License' in its name.

#### Samples

<details>

<summary>Base template</summary>

```text
The recipe `license` should not include the word "License".
```

</details>

_No samples available_

<a id='R-011'></a>
### `R-011`: `RecipeTooManyEmptyLines`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Recipe files should end with a single empty line, not more.

#### Samples

<details>

<summary>Base template</summary>

```text
There are {n_lines} too many lines.  There should be one empty line at the end of the file.
```

</details>

_No samples available_

<a id='R-012'></a>
### `R-012`: `RecipeTooFewEmptyLines`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Recipe files should end with a single empty line.

#### Samples

<details>

<summary>Base template</summary>

```text
There are too few lines.  There should be one empty line at the end of the file.
```

</details>

_No samples available_

<a id='R-013'></a>
### `R-013`: `RecipeLicenseFamily`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The field `license_file` must be always present.

#### Samples

<details>

<summary>Base template</summary>

```text
license_file entry is missing, but is required.
```

</details>

_No samples available_

<a id='R-014'></a>
### `R-014`: `RecipeName`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The recipe `name` can only contain certain characters:

- lowercase ASCII letters (`a-z`)
- digits (`0-9`)
- underscores, hyphens and dots (`_`, `-`, `.`)

#### Samples

<details>

<summary>Base template</summary>

```text
Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed
```

</details>

_No samples available_

<a id='R-015'></a>
### `R-015`: `RecipeMissingVersion`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The package `version` field is required.

#### Samples

<details>

<summary>Base template</summary>

```text
Package version is missing.
```

</details>

_No samples available_

<a id='R-016'></a>
### `R-016`: `RecipeInvalidVersion`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The package `version` field must be a valid version string.

#### Samples

<details>

<summary>Base template</summary>

```text
Package version {version} doesn't match conda spec: {error}
```

</details>

_No samples available_

<a id='R-017'></a>
### `R-017`: `RecipePinnedNumpy`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

See <https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy>

#### Samples

<details>

<summary>Base template</summary>

```text
Using pinned numpy packages is a deprecated pattern.  Consider using the method outlined [here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy).
```

</details>

_No samples available_

<a id='R-018'></a>
### `R-018`: `RecipeUnexpectedSubsection`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

This check ensures that the passed recipe conforms to the expected recipe v0 schema.

See schema in [`conda_build.metadata.FIELDS`](
https://github.com/conda/conda-build/blob/25.9.0/conda_build/metadata.py#L619)

#### Samples

<details>

<summary>Base template</summary>

```text
The {section} section contained an unexpected subsection name. {subsection} is not a valid subsection name.
```

</details>

_No samples available_

<a id='R-019'></a>
### `R-019`: `RecipeSourceHash`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

All recipe source URLs must have a hash checksum for integrity checks.

#### Samples

<details>

<summary>Base template</summary>

```text
When defining a source/url please add a sha256, sha1 or md5 checksum (sha256 preferably).
```

</details>

_No samples available_

<a id='R-020'></a>
### `R-020`: `RecipeNoarchValue`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The `build.noarch` field can only take `python` or `generic` as a value.

#### Samples

<details>

<summary>Base template</summary>

```text
Invalid `noarch` value `{given}`. Should be one of `{valid}`.
```

</details>

_No samples available_

<a id='R-021'></a>
### `R-021`: `RecipeRequirementJoinVersionOperator`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

conda recipes should use the three-field matchspec syntax to express requirements:
`name [version [build]]`. This means having no spaces between operator and version
literals.

#### Samples

<details>

<summary>Base template</summary>

```text
``requirements: {section}: {requirement}`` should not contain a space between relational operator and the version, i.e. ``{name} {pin}``
```

</details>

_No samples available_

<a id='R-022'></a>
### `R-022`: `RecipeRequirementSeparateNameVersion`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

conda recipes should use the three-field matchspec syntax to express requirements:
`name [version [build]]`. This means having a space between name and version.

#### Samples

<details>

<summary>Base template</summary>

```text
``requirements: {section}: {requirement}`` must contain a space between the name and the pin, i.e. ``{name} {pin}``
```

</details>

_No samples available_

<a id='R-023'></a>
### `R-023`: `RecipeLanguageHostRun`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Packages may depend on certain languages (e.g. Python, R) that require depending
on the language runtime both in `host` and `run`.

#### Samples

<details>

<summary>Base template</summary>

```text
If {language} is a host requirement, it should be a run requirement.
```

</details>

_No samples available_

<a id='R-024'></a>
### `R-024`: `RecipeLanguageHostRunUnpinned`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Packages may depend on certain languages (e.g. Python, R) that require depending
on the language runtime both in `host` and `run`. They should not pin it to a
particular version when the package is not `noarch`.

#### Samples

<details>

<summary>Base template</summary>

```text
Non noarch packages should have {language} requirement without any version constraints.
```

</details>

_No samples available_

<a id='R-025'></a>
### `R-025`: `RecipeJinjaExpression`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Jinja expressions should add a space between the double curly braces.

#### Samples

<details>

<summary>Base template</summary>

```text
Jinja2 variable references are suggested to take a ``{dollar}{{{{<one space><variable name><one space>}}}}`` form. See lines {lines}.
```

</details>

_No samples available_

<a id='R-026'></a>
### `R-026`: `RecipePythonLowerBound`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Noarch Python recipes should always pin the lower bound on their `python` requirement.

#### Samples

<details>

<summary>Base template</summary>

```text
noarch: python recipes are required to have a lower bound on the python version. Typically this means putting `python >={{{{ python_min }}}}` in the `run` section of your recipe. You may also want to check the upstream source for the package's Python compatibility.
```

</details>

_No samples available_

<a id='R-027'></a>
### `R-027`: `RecipePinSubpackagePinCompatible`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The Jinja functions `pin_subpackage` and `pin_compatible` may be confused
because both would add version constraints to a package name. However, they
have different purposes.

- `pin_subpackage()` must be used when the package to be pinned is a known output
  in the current recipe.
- `pin_compatible()` must be used when the package to be pinned is _not_ an output
  of the current recipe.

#### Samples

<details>

<summary>Base template</summary>

```text
{should_use} should be used instead of {in_use} for `{pin}` because it is {what} known outputs of this recipe: {subpackages}.
```

</details>

_No samples available_

<a id='R-028'></a>
### `R-028`: `RecipeCompiledWheelsNotAllowed`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Python wheels are often discouraged as package sources. This is especially the case
for compiled wheels, which are forbidden.

#### Samples

<details>

<summary>Base template</summary>

```text
Detected compiled wheel(s) in source: {urls}. This is disallowed. All packages should be built from source except in rare and exceptional cases.
```

</details>

_No samples available_

<a id='R-029'></a>
### `R-029`: `RecipePureWheelsNotAllowed`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Python wheels are often discouraged as package sources. This is also the case
for pure Python wheels when building non-noarch packages.

#### Samples

<details>

<summary>Base template</summary>

```text
Detected pure Python wheel(s) in source: {urls}. This is discouraged. Please consider using a source distribution (sdist) instead.
```

</details>

_No samples available_

<a id='R-030'></a>
### `R-030`: `RecipePureWheelsNotAllowedNoarch`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Python wheels are often discouraged as package sources. However, pure Python
wheels may be used as a source for noarch Python packages, although sdists are preferred.

#### Samples

<details>

<summary>Base template</summary>

```text
Detected pure Python wheel(s) in source: {urls}. This is generally ok for pure Python wheels and noarch=python packages but it's preferred to use a source distribution (sdist) if possible.
```

</details>

_No samples available_

<a id='R-031'></a>
### `R-031`: `RecipeRustLicenses`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

<https://conda-forge.org/docs/maintainer/adding_pkgs/#rust>

#### Samples

<details>

<summary>Base template</summary>

```text
Rust packages must include the licenses of the Rust dependencies. For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust
```

</details>

_No samples available_

<a id='R-032'></a>
### `R-032`: `RecipeGoLicenses`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

<https://conda-forge.org/docs/maintainer/adding_pkgs/#go>

#### Samples

<details>

<summary>Base template</summary>

```text
Go packages must include the licenses of the Go dependencies. For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go
```

</details>

_No samples available_

<a id='R-033'></a>
### `R-033`: `RecipeStdlibJinja`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
This recipe is using a compiler, which now requires adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}` as well. Note that this rule applies to each output of the recipe using a compiler. For further details, please see https://github.com/conda-forge/conda-forge.github.io/issues/2102.
```

</details>

_No samples available_

<a id='R-034'></a>
### `R-034`: `RecipeStdlibSysroot`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
You're setting a requirement on sysroot_linux-<arch> directly; this should now be done by adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}`, and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the respective platform as necessary. For further details, please see https://github.com/conda-forge/conda-forge.github.io/issues/2102.
```

</details>

_No samples available_

<a id='R-035'></a>
### `R-035`: `RecipeStdlibOsx`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
You're setting a constraint on the `__osx` virtual package directly; this should now be done by adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}`, and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the respective platform as necessary. For further details, please see https://conda-forge.org/docs/maintainer/knowledge_base/#requiring-newer-macos-sdks.
```

</details>

_No samples available_

<a id='R-036'></a>
### `R-036`: `RecipeNotParsableLint`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The conda recipe should be parsable by at least one backend.
If none can parse it, this constitutes an error that needs to be remediated.

#### Samples

<details>

<summary>Base template</summary>

```text
The recipe is not parsable by any of the known recipe parsers ({parsers}). Please check the logs for more information and ensure your recipe can be parsed.
```

</details>

_No samples available_

<a id='R-037'></a>
### `R-037`: `RecipeNotParsableHint`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

The conda recipe should be parsable by at least one backend.
Sometimes, only some backends fail, which is not critical, but should be looked into.

#### Samples

<details>

<summary>Base template</summary>

_Message generated dynamically. Template not available._

</details>

_No samples available_

<a id='R-038'></a>
### `R-038`: `RecipePythonIsAbi3Bool`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
The `is_abi3` variant variable is now a boolean value instead of a string (i.e., 'true' or 'false'). Please change syntax like `is_abi3 == 'true' to `is_abi3`.
```

</details>

_No samples available_

<a id='R-039'></a>
### `R-039`: `RecipeExtraFeedstockNameSuffix`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
The feedstock-name in the `extra` section must not end with '-feedstock'. The '-feedstock' suffix is automatically appended during feedstock creation.
```

</details>

_No samples available_

<a id='R-040'></a>
### `R-040`: `RecipeVersionParsedAsFloat`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
{key} has a value that is interpreted as a floating-point number. Please quote it (like `"{value}"`{v0_hint}) to ensure that it is interpreted as string and preserved exactly.
```

</details>

_No samples available_

<a id='R-041'></a>
### `R-041`: `RecipeSuggestNoarch`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

`noarch` packages are strongly preferred when possible.
See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds.

#### Samples

<details>

<summary>Base template</summary>

```text
Whenever possible python packages should use noarch. See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds
```

</details>

_No samples available_

<a id='R-042'></a>
### `R-042`: `ScriptShellcheckReport`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

This issue is raised when `shellcheck` is enabled and detects problems
in your build `.sh` scripts.

See https://www.shellcheck.net/wiki/ for details on the shellcheck error codes.

#### Samples

<details>

<summary>Base template</summary>

_Message generated dynamically. Template not available._

</details>

_No samples available_

<a id='R-043'></a>
### `R-043`: `ScriptShellcheckFailure`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

This issue is raised when `shellcheck` is enabled but could not
run successfully (something went wrong).

#### Samples

<details>

<summary>Base template</summary>

```text
There have been errors while scanning with shellcheck.
```

</details>

_No samples available_

<a id='R-044'></a>
### `R-044`: `RecipeLicenseSPDX`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

The `license` field must be a valid SPDX identifier.

See list at [`licenses.txt`](https://github.com/conda-forge/conda-smithy/blob/main/conda_smithy/linter/licenses.txt).

#### Samples

<details>

<summary>Base template</summary>

```text
License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression.

Documentation on acceptable licenses can be found [here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions ).
```

</details>

_No samples available_

<a id='R-045'></a>
### `R-045`: `RecipeInvalidLicenseException`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

The `license` field may accept some SPDX exception expressions, as controlled
in [this file](https://github.com/conda-forge/conda-smithy/blob/main/conda_smithy/linter/license_exceptions.txt)

#### Samples

<details>

<summary>Base template</summary>

```text
License exception is not an SPDX exception.

Documentation on acceptable licenses can be found [here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions ).
```

</details>

_No samples available_

<a id='R-046'></a>
### `R-046`: `RecipePythonBuildBackendHost`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Build backends in Python packages must be explictly added to `host`.

#### Samples

<details>

<summary>Base template</summary>

```text
No valid build backend found for Python recipe for package `{package_name}` using `pip`. Python recipes using `pip` need to explicitly specify a build backend in the `host` section. If your recipe has built with only `pip` in the `host` section in the past, you likely should add `setuptools` to the `host` section of your recipe.
```

</details>

_No samples available_

<a id='R-047'></a>
### `R-047`: `RecipePythonMinPin`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Python packages should depend on certain `>={min_version}` at runtime,
but build and test against `{min_version}.*`.

#### Samples

<details>

<summary>Base template</summary>

```text
`noarch: python` recipes should usually follow the syntax in our [documentation](https://conda-forge.org/docs/maintainer/knowledge_base/#noarch-python) for specifying the Python version.
{recommendations}
- If the package requires a newer Python version than the currently supported minimum version on `conda-forge`, you can override the `python_min` variable by adding a Jinja2 `set` statement at the top of your recipe (or using an equivalent `context` variable for v1 recipes).
```

</details>

_No samples available_

<a id='R-048'></a>
### `R-048`: `RecipeSpaceSeparatedSpecs`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Prefer `name [version [build]]` match spec syntax.

#### Samples

<details>

<summary>Base template</summary>

```text
{output} output has some malformed specs:
{bad_specs_list}
Requirement spec fields should match the syntax `name [version [build]]`to avoid known issues in conda-build. For example, instead of `name =version=build`, use `name version.* build`. There should be no spaces between version operators and versions either: `python >= 3.8` should be `python >=3.8`.
```

</details>

_No samples available_

<a id='R-049'></a>
### `R-049`: `RecipeOsVersion`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Prefer `name [version [build]]` match spec syntax.

#### Samples

<details>

<summary>Base template</summary>

```text
The feedstock is lowering the image versions for one or more platforms: {platforms} (the default is {default}). Unless you are in the very rare case of repackaging binary artifacts, consider removing these overrides from conda-forge.yml in the top feedstock directory.
```

</details>

_No samples available_

<a id='R-050'></a>
### `R-050`: `RecipeUsePip`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Python packages should be built with `pip install ...`, not `python setup.py install`,
which is deprecated.

#### Samples

<details>

<summary>Base template</summary>

```text
Whenever possible python packages should use pip. See https://conda-forge.org/docs/maintainer/adding_pkgs.html#use-pip
```

</details>

_No samples available_

<a id='R-051'></a>
### `R-051`: `RecipeUsePyPiOrg`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Grayskull and the conda-forge example recipe used to have pypi.io as a default,
but the canonical URL is now PyPI.org.

See https://github.com/conda-forge/staged-recipes/pull/27946.

#### Samples

<details>

<summary>Base template</summary>

```text
PyPI default URL is now pypi.org, and not pypi.io. You may want to update the default source url.
```

</details>

_No samples available_

<a id='R0'></a>
## `R0`: Only `meta.yaml`

<a id='R0-001'></a>
### `R0-001`: `RecipeFormattedSelectors`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Recipe format v0 (`meta.yaml`) supports the notion of line selectors
as trailing comments:

```yaml
build:
  skip: true  # [not win]
```

These must be formatted with two spaces before the `#` symbol, followed
by one space before the opening square bracket `[`, followed by no spaces.
The closing bracket must not be surrounded by spaces either.

#### Samples

<details>

<summary>Base template</summary>

```text
Selectors are suggested to take a ``<two spaces>#<one space>[<expression>]`` form. See lines {lines}
```

</details>

_No samples available_

<a id='R0-002'></a>
### `R0-002`: `RecipeOldPythonSelectorsLint`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Recipe v0 selectors used to include one Python version selector
per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
This was deprecated in favor of the `py` integer, which is preferred.

#### Samples

<details>

<summary>Base template</summary>

```text
Old-style Python selectors (py27, py35, etc) are only available for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. See lines {lines}
```

</details>

_No samples available_

<a id='R0-003'></a>
### `R0-003`: `RecipeOldPythonSelectorsHint`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

Recipe v0 selectors (see [`R0-002`](#r0-002)) used to include one Python
version selector per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
This was deprecated in favor of the `py` integer, which is preferred.

#### Samples

<details>

<summary>Base template</summary>

```text
Old-style Python selectors (py27, py34, py35, py36) are deprecated. Instead, consider using the int ``py``. For example: ``# [py>=36]``. See lines {lines}
```

</details>

_No samples available_

<a id='R0-004'></a>
### `R0-004`: `RecipeNoarchSelectorsV0`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Noarch packages are not generally compatible with v0 selectors

#### Samples

<details>

<summary>Base template</summary>

```text
`noarch` packages can't have {skips}selectors. If the selectors are necessary, please remove `noarch: {noarch}`, or selector on line {line_number}:
{line}
```

</details>

_No samples available_

<a id='R0-005'></a>
### `R0-005`: `RecipeJinjaDefinitions`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

In v0 recipes, Jinja definitions must follow a particular style.

#### Samples

<details>

<summary>Base template</summary>

```text
Jinja2 variable definitions are suggested to take a ``{{%<one space>set<one space><variable name><one space>=<one space><expression><one space>%}}`` form. See lines {lines}
```

</details>

_No samples available_

<a id='R0-006'></a>
### `R0-006`: `RecipeLegacyToolchain`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

The `toolchain` package is deprecated. Use compilers as outlined in
<https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers>.

#### Samples

<details>

<summary>Base template</summary>

```text
Using toolchain directly in this manner is deprecated.  Consider using the compilers outlined [here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers).
```

</details>

_No samples available_

<a id='R1'></a>
## `R1`: Only `recipe.yaml`

<a id='R1-001'></a>
### `R1-001`: `RecipeNoCommentSelectors`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Recipe v0 selectors (see [`R0-002`](#r0-002)) are not supported in v1 recipes.

#### Samples

<details>

<summary>Base template</summary>

```text
Selectors in comment form no longer work in v1 recipes. Instead, if / then / else maps must be used. See lines {lines}.
```

</details>

_No samples available_

<a id='R1-002'></a>
### `R1-002`: `RecipeNoarchSelectorsV1`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

Noarch packages are not generally compatible with v1 conditional blocks.

#### Samples

<details>

<summary>Base template</summary>

```text
`noarch` packages can't have {skips}selectors. If the selectors are necessary, please remove `noarch: {noarch}`.
```

</details>

_No samples available_

<a id='R1-003'></a>
### `R1-003`: `RecipeRattlerBldBat`

- Type: ℹ️ Hint
- Added in: conda-smithy <3.28.

`rattler-build` does not use `bld.bat` scripts, but `build.bat`.

#### Samples

<details>

<summary>Base template</summary>

```text
Found `bld.bat` in recipe directory, but this is a recipe v1 (rattler-build recipe). rattler-build uses `build.bat` instead of `bld.bat` for Windows builds. Consider renaming `bld.bat` to `build.bat`.
```

</details>

_No samples available_

<a id='RC'></a>
## `RC`: All recipe variants files

<a id='RC-000'></a>
### `RC-000`: `CBCMacOSDeploymentTargetRename`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
The `MACOSX_DEPLOYMENT_TARGET` key in {recipe_config_file} needs to be removed or replaced by `c_stdlib_version`, appropriately restricted to osx
```

</details>

_No samples available_

<a id='RC-001'></a>
### `RC-001`: `CBCMacOSDeploymentTargetBelow`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
You are setting `c_stdlib_version` on osx below the current global baseline in conda-forge ({baseline_version}).
```

</details>

_No samples available_

<a id='RC-002'></a>
### `RC-002`: `CBCMacOSDeploymentTargetBelowStdlib`

- Type: 🚨 Lint
- Added in: conda-smithy <3.28.

https://github.com/conda-forge/conda-forge.github.io/issues/2102

#### Samples

<details>

<summary>Base template</summary>

```text
You are setting `MACOSX_SDK_VERSION` below `c_stdlib_version`, in conda_build_config.yaml which is not possible! Please ensure `MACOSX_SDK_VERSION` is at least `c_stdlib_version` (you can leave it out if it is equal).
If you are not setting `c_stdlib_version` yourself, this means you are requesting a version below the current global baseline in conda-forge ({baseline}). If this is the intention, you also need to override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally.
```

</details>

_No samples available_
