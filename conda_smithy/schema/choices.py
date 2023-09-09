from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Platforms(str, Enum):
    linux_64 = "linux_64"
    linux_aarch64 = "linux_aarch64"
    linux_ppc64le = "linux_ppc64le"
    linux_armv7l = "linux_armv7l"
    linux_s390x = "linux_s390x"
    win_64 = "win_64"
    osx_64 = "osx_64"
    osx_arm64 = "osx_arm64"
    # Aliases
    linux = "linux"
    win = "win"
    osx = "osx"


class ChannelPriorityConfig(str, Enum):
    STRICT = "strict"
    FLEXIBLE = "flexible"
    DISABLED = "disabled"


class DefaultTestPlatforms(str, Enum):
    all = "all"
    native_only = "native_only"
    native_and_emulated = "native_and_emulated"
    emulated_only = "emulated_only"


class BotConfigAutoMergeChoice(str, Enum):
    VERSION = "version"
    MIGRATION = "migration"


class BotConfigSkipRenderChoices(str, Enum):
    GITIGNORE = ".gitignore"
    GITATTRIBUTES = ".gitattributes"
    README = "README.md"
    LICENSE = "LICENSE.txt"
    GITHUB_WORKFLOWS = ".github/workflows"


class BotConfigInspectionChoice(str, Enum):
    HINT = "hint"
    HINT_ALL = "hint-all"
    HINT_SOURCE = "hint-source"
    HINT_GRAYSKULL = "hint-grayskull"
    UPDATE_ALL = "update-all"
    UPDATE_SOURCE = "update-source"
    UPDATE_GRAYSKULL = "update-grayskull"
