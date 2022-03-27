
**Changed:**

* skip_render can match Path().parents of files being rendered
  i.e. '.github' in list prevents rendering .github in toplevel
  and any files below .github/

**Fixed:**

* skip_render can prevent github webservices from rendering

