from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AzureSettings(BaseModel):
    pool: Dict[str, str]
    timeoutInMinutes: int
    variables: Optional[Dict[str, str]]


class AzureConfig(BaseModel):
    settings_linux: AzureSettings
    settings_osx: AzureSettings
    settings_win: AzureSettings
    force: bool = False
    project_name: str = "feedstock-builds"
    project_id: str = "84710dde-1620-425b-80d0-4cf5baca359d"
    timeout_minutes: Optional[int] = None
    store_build_artifacts: bool = False
    max_parallel: int = 50

    class Config:
        # The field descriptions and docstrings are provided using the multi-line strings.
        title = "azure"
        description = (
            "This dictates the behavior of the Azure Pipelines CI service. It is a "
            "mapping for Azure-specific configuration options."
        )
        extra = "allow"


class ProviderConfig(BaseModel):
    linux_64: List[str]
    osx_64: List[str]
    win_64: List[str]
    linux_aarch64: Optional[None] = None
    linux_ppc64le: Optional[None] = None
    linux_armv7l: Optional[None] = None
    linux_s390x: Optional[None] = None
    linux: Optional[None] = None
    osx: Optional[None] = None
    win: Optional[None] = None


class BuildPlatformConfig(BaseModel):
    linux_64: str
    linux_aarch64: str
    linux_ppc64le: str
    linux_s390x: str
    linux_armv7l: str
    win_64: str
    osx_64: str


class ConfigModel(BaseModel):
    docker: Dict[str, str]
    templates: Dict[str, str]
    drone: Dict[str, str]
    woodpecker: Dict[str, str]
    travis: Dict[str, str]
    circle: Dict[str, str]
    config_version: str
    appveyor: Dict[str, str]
    azure: AzureConfig
    provider: ProviderConfig
    build_platform: BuildPlatformConfig
    noarch_platforms: List[str]
    os_version: Dict[str, Optional[str]]
    test: Optional[str]
    test_on_native_only: bool = False
    choco: List[str] = []
    idle_timeout_minutes: Optional[int] = None
    compiler_stack: str
    min_py_ver: str
    max_py_ver: str
    min_r_ver: str
    max_r_ver: str
    channels: Dict[str, List[List[str]]]
    github: Dict[str, str]
    github_actions: Dict[str, bool]
    recipe_dir: str
    skip_render: List[str] = []
    bot: Dict[str, bool]
    conda_forge_output_validation: bool = False
    private_upload: bool = False
    secrets: List[str] = []
    build_with_mambabuild: bool = True
    clone_depth: Optional[int] = None
    remote_ci_setup: List[str]

    class Config:
        # This allows Pydantic to use the default values from the model if the key is missing in the input dictionary.
        extra = "allow"
