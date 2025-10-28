# Linter messages

<a id='R-000'></a>
## `R-000`: `RecipeUnexpectedSection`


Recipe files must not contain unknown top-level keys.

<details>

<summary>Lint message</summary>

```text
The top level meta key {section} is unexpected
```

</details>

<a id='R-001'></a>
## `R-001`: `RecipeSectionOrder`


The top-level sections of a recipe file must always follow the same order.

<details>

<summary>Lint message</summary>

```text
The top level meta keys are in an unexpected order. Expecting {order}.
```

</details>

<a id='R-002'></a>
## `R-002`: `RecipeMissingAboutItem`


The `about` section requires three fields: homepage (`home` in v1), license, and summary.

<details>

<summary>Lint message</summary>

```text
The {item} item is expected in the about section.
```

</details>

<a id='R-003'></a>
## `R-003`: `RecipeNoMaintainers`


All recipes must list at least one maintainer under `extra/recipe-maintainers`.

<details>

<summary>Lint message</summary>

```text
The recipe could do with some maintainers listed in the `extra/recipe-maintainers` section.
```

</details>

<a id='R-004'></a>
## `R-004`: `RecipeMaintainersMustBeList`


The `extra/recipe-maintainers` only accepts a list of strings as a value.

<details>

<summary>Lint message</summary>

```text
Recipe maintainers should be a json list.
```

</details>

<a id='R-005'></a>
## `R-005`: `RecipeRequiredTests`


All recipes must have a non-empty `test` section.

<details>

<summary>Lint message</summary>

```text
The recipe must have some tests.
```

</details>

<a id='R-006'></a>
## `R-006`: `RecipeRecommendedTests`


All recipes must have a non-empty `test` section.

<details>

<summary>Hint message</summary>

```text
It looks like the '{output}' output doesn't have any tests.
```

</details>

<a id='R-007'></a>
## `R-007`: `RecipeUnknownLicense`


All recipes must have a license identifier, but it can't be "unknown".

<details>

<summary>Lint message</summary>

```text
The recipe license cannot be unknown.
```

</details>

<a id='R0-001'></a>
## `R0-001`: `RecipeFormattedSelectors`


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
## `R0-002`: `RecipeOldPythonSelectorsLint`


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
## `R0-003`: `RecipeOldPythonSelectorsHint`


Recipe v0 selectors (see [`R0-002`](#r0-002)) used to include one Python
version selector per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
This was deprecated in favor of the `py` integer, which is preferred.

<details>

<summary>Hint message</summary>

```text
Old-style Python selectors (py27, py34, py35, py36) are deprecated. Instead, consider using the int ``py``. For example: ``# [py>=36]``. See lines {lines}
```

</details>
