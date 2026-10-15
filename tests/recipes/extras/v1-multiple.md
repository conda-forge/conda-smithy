| Install | Optional Dependencies |
| --- | --- |
| `b-has-extras[extras=simple]` | `a-simple-package` |
| `c-has-nested-extras[extras=complex]` | `a-simple-package` `d-something-else` |
| `c-has-nested-extras[extras=simple]` | `b-has-extras[extras=simple]` |
| `e-has-more-nested-extras[extras=extra-complex]` | `a-simple-package` `c-has-nested-extras[extras=[complex,simple]]` |
| `e-has-more-nested-extras[extras=simple]` | `b-has-extras[extras=simple]` |
