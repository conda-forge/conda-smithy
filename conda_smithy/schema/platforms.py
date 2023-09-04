from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


Platforms = Literal[
    "linux_64",
    "linux_aarch64",
    "linux_ppc64le",
    "linux_armv7l",
    "linux_s390x",
    "win_64",
    "osx_64",
    "osx_arm64",
    # Aliases
    "linux",
    "win",
    "osx",
]


class PlatformUniqueConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra platform-specific configuration options",
        default=False,
    )
