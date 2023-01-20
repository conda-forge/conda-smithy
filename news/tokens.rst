**Added:**

* Added code to support multiple tokens per feedstock and unique tokens per CI-feedstock combination.
* Added a function and CLI tool to remove feedstock tokens from the token registry.

**Changed:**

* Feedstock token registry json blob format has changed to support multiple tokens. ``conda-smithy`` understands
  both formats and will convert json blobs on-the-fly as needed.
* Feedstock token operations now use GitHub API requests instead of git repos.
