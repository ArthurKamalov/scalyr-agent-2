import pathlib as pl
from typing import Type

import pytest

from agent_build_refactored.tools import LocalRegistryContainer
from agent_build_refactored.docker_image_builders import (
    ContainerImageBuilder,
    ALL_IMAGE_BUILDERS
)


def pytest_addoption(parser):
    parser.addoption(
        "--images-registry",
        dest="images_registry",
        required=False,
        help="Path to directory with registry data root which contains image to test."
    )
    parser.addoption(
        "--image-builder-name",
        dest="image_builder_name",
        required=True,
        choices=list(ALL_IMAGE_BUILDERS.keys()),
        help="Name of the image builder that builds image to test."
    )


@pytest.fixture(scope="session")
def image_builder_name(request):
    return request.config.option.image_builder_name


@pytest.fixture(scope="session")
def image_builder_cls(image_builder_name) -> Type[ContainerImageBuilder]:
    return ALL_IMAGE_BUILDERS[image_builder_name]


@pytest.fixture(scope="session")
def source_registry_path(image_builder_cls, request, tmp_path_factory):
    """
    Fixture with path to the registry with pre-built agent images.
    """

    # We can specify path to existing image registry to reuse images stored in there. (Used in CI/CD testing.)
    if request.config.option.images_registry:
        return pl.Path(request.config.option.images_registry)

    # Or create registry from scratch (local testing)
    builder = image_builder_cls()
    builder_output = tmp_path_factory.mktemp("builder-output")
    builder.build(output_registry_dir=builder_output)
    return builder_output


@pytest.fixture(scope="session")
def all_image_names_to_publish(
    image_builder_cls,
    source_registry_path
):
    """
    Registry that contains target image. It may be an externally specified one, or if omitted,
        new local registry with image is created.
    """

    with LocalRegistryContainer(
        name="images_registry",
        registry_port=0,
    ) as reg_container:

        registry_host = f"localhost:{reg_container.real_registry_port}"

        builder = image_builder_cls()

        all_published_image_names = builder.publish(
            src_registry_data_path=source_registry_path,
            tags=["test"],
            user="test_user",
            dst_registry_host=registry_host,
            dst_registry_tls_skip_verify=True,
        )

        yield all_published_image_names


@pytest.fixture(scope="session")
def image_name(all_image_names_to_publish):
    # Get the first name of of all available names to use it for all main tests.
    return all_image_names_to_publish[0]
