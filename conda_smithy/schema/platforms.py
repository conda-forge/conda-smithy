from enum import Enum
from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class Platforms(str, Enum):
    linux_64 = "linux_64"
    linux_aarch64 = "linux_aarch64"
    linux_ppc64le = "linux_ppc64le"
    linux_armv7l = "linux_armv7l"
    linux_s390x = "linux_s390x"
    win_64 = "win_64"
    osx_64 = "osx_64"
    # win = "win"  # should this be added as a platform? or should I consider it as an alias of win_64? if so, how to address cases like win = win for the platform field? (e.g r-rebus-feedstock)
    # osx_arm64 = "osx_arm64"

    @classmethod
    @model_validator(mode="before")
    def check_platforms(cls, values):
        if not values:
            return values

        # Check that the build platforms are valid
        for k, v in values.items():
            # key and value must comply with <platform>_<arch> format
            try:
                build_platform = k.split("_")[0]
                target_platform = v.split("_")[0]
            except IndexError:
                raise ValueError(
                    f"Build platform {k} and target platform {v} must comply with <platform>_<arch> format"
                )
            return values


class MacOsxConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra macOSX-specific configuration options",
        default=False,
    )


class WinConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra Windows-specific configuration options",
        default=False,
    )


class LinuxConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra Linux-specific configuration options",
        default=False,
    )


class Aarch64Config(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra ARM-specific configuration options",
        default=False,
    )


class Ppc64leConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra PPC-specific configuration options",
        default=False,
    )
