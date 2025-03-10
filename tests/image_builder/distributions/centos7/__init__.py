# Copyright 2014-2020 Scalyr Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from scalyr_agent.__scalyr__ import get_install_root
from tests.utils.compat import Path
from tests.image_builder.distributions.fpm_package_builder import FpmPackageBuilder
from tests.utils.image_builder import AgentImageBuilder
from tests.image_builder.distributions.base import (
    create_distribution_base_image_name,
    create_distribution_image_name,
)

DISTRIBUTION_NAME = "centos7"


class CentOSBuilderBase(AgentImageBuilder):
    IMAGE_TAG = create_distribution_base_image_name(DISTRIBUTION_NAME)
    DOCKERFILE = Path(__file__).parent / "Dockerfile.base"
    INCLUDE_PATHS = [
        Path(get_install_root(), "dev-requirements.txt"),
        Path(get_install_root(), "agent_build"),
    ]


class CentOSBuilder(AgentImageBuilder):
    IMAGE_TAG = create_distribution_image_name(DISTRIBUTION_NAME)
    DOCKERFILE = Path(__file__).parent / "Dockerfile"
    REQUIRED_IMAGES = [FpmPackageBuilder, CentOSBuilderBase]
    REQUIRED_CHECKSUM_IMAGES = [CentOSBuilderBase]
    COPY_AGENT_SOURCE = True
    IGNORE_CACHING = True
