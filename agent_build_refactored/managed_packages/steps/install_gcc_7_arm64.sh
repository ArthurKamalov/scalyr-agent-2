#!/usr/bin/env bash
# Copyright 2014-2022 Scalyr Inc.
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

# This script is meant to be executed by the instance of the 'agent_build_refactored.tools.runner.RunnerStep' class.
# Every RunnerStep provides common environment variables to its script:
#   SOURCE_ROOT: Path to the projects root.
#   STEP_OUTPUT_PATH: Path to the step's output directory.
#
# This script prepares base build environment for the X86_64 linux GLIBC binary packages, it expects to be run in
# Centos 6 to compile against lower GLIBS (2.12).
# It switches to Centos 6 vault repository sources (since its original sources are now disabled)
# and installs newer version of gcc.

set -e

# RHSCL is installed, so we can install newer tools, such as gcc-7
yum install -y centos-release-scl
yum install -y devtoolset-7

# Remove this preinstalled packages, since we build and install those libraries from source.
yum remove -y help2man m4 perl

echo "source /opt/rh/devtoolset-7/enable" >> ~/.bashrc
# shellcheck disable=SC2016
echo 'export LD_LIBRARY_PATH="/usr/local/lib:/usr/local/lib64:${LD_LIBRARY_PATH}"' >> ~/.bashrc

yum clean all
rm -rf /var/cache/yum
