import json
import logging

logger = logging.getLogger(__name__)


class ResolveFallback:
    """
    Wrapper that implements a tiny subset of :class:`conda_build.conda_interface.Resolve`.

    Calls are first tried using mamba and we switch to conda_build.conda_interface on failure.
    """

    def __init__(self):
        self.use_fallback = False
        self.conda_resolve = None
        self.mamba_pool = None
        self.mamba_repos = None

    def _load_mamba_repos(self):
        import mamba.mamba_api as api
        from mamba.utils import get_index, init_api_context

        if self.mamba_repos is None:
            if self.mamba_pool is None:
                init_api_context()
                self.mamba_pool = api.Pool()

            index = get_index(("conda-forge",), prepend=False)
            self.mamba_repos = []

            for subdir, channel in index:
                if subdir.loaded() == False and channel.platform != "noarch":
                    # ignore non-loaded subdir if channel is != noarch
                    continue

                repo = api.Repo(
                    self.mamba_pool,
                    str(channel),
                    subdir.cache_path(),
                    channel.url(with_credentials=True),
                )
                repo.set_priority(0, 0)
                self.mamba_repos.append(repo)

    def _load_conda_resolve(self):
        import conda_build.conda_interface

        if self.conda_resolve is None:
            index = conda_build.conda_interface.get_index(
                channel_urls=["conda-forge"]
            )
            self.conda_resolve = conda_build.conda_interface.Resolve(index)

    def get_pkgs(self, match_spec):
        if self.use_fallback:
            self._load_conda_resolve()
            return self.conda_resolve.get_pkgs(match_spec)

        try:
            import mamba.mamba_api as api

            self._load_mamba_repos()
            solver = api.Solver(self.mamba_pool, [(api.MAMBA_NO_DEPS, True)])
            solver.set_postsolve_flags([(api.MAMBA_NO_DEPS, True)])
            solver.add_jobs(
                [match_spec.conda_build_form()], api.SOLVER_INSTALL
            )
            success = solver.solve()

            package_cache = api.MultiPackageCache([""])
            transaction = api.Transaction(solver, package_cache)
            pkg_information = json.loads(transaction.to_conda()[1][0][2])

            import conda.models.records

            return [conda.models.records.PackageRecord(**pkg_information)]
        except:
            logger.warning(
                "get_pkgs using mamba failed, falling back to conda",
                exc_info=True,
            )
            self.use_fallback = True
            return self.get_pkgs(match_spec)
