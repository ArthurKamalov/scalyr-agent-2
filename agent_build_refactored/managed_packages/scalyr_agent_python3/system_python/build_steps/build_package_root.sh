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


set -e

mkdir -p "${STEP_OUTPUT_PATH}/root/usr/lib/${SUBDIR_NAME}/requirements/python3/bin"

# Copy wrapper for Python interpreter executable.
cp -a "${SOURCE_ROOT}/agent_build_refactored/managed_packages/scalyr_agent_python3/system_python/files/python3" "${STEP_OUTPUT_PATH}/root/usr/lib/${SUBDIR_NAME}/requirements/python3/bin/python3"
