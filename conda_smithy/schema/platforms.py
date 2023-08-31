from pydantic import BaseModel, Field, model_validator


class Platforms(BaseModel):
    linux_64: str = Field(
        alias="linux",
        default="linux-64",
    )
    linux_aarch64: str = Field(
        default="linux-aarch64",
    )
    linux_ppc64le: str = Field(
        default="linux-ppc64le",
    )
    linux_armv7l: str = Field(
        default="linux-armv7l",
    )
    linux_s390x: str = Field(
        default="linux-s390x",
    )
    win_64: str = Field(
        alias="win",
        default="win-64",
    )
    osx_64: str = Field(
        alias="osx",
        default="osx-64",
    )
    osx_arm64: str = Field(
        default="osx-arm64",
    )

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
