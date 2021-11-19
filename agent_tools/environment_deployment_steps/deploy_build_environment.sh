#!/bin/bash
# Copyright 2014-2021 Scalyr Inc.
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

# This script is used by "ShellScriptDeploymentStep"
# (See more in class "ShellScriptDeploymentStep" in the "agent_tools/environment_deployments.py"

set -e

PARENT_DIR="$(dirname "$0")"
SOURCE_ROOT=$(dirname "$(dirname "$PARENT_DIR")")

source "$PARENT_DIR/cache_lib.sh"

pip_cache_dir="$(python3 -m pip cache dir)"

# Reuse cached pip cache if exists.
restore_from_cache pipi "$pip_cache_dir"

python3 -m pip install -r "${SOURCE_ROOT}/agent_build/requirement-files/main-requirements.txt"
python3 -m pip install -r "${SOURCE_ROOT}/agent_build/requirement-files/monitors-requirements.txt"
python3 -m pip install -r "${SOURCE_ROOT}/agent_build/requirement-files/compression-requirements.txt"
python3 -m pip install -r "${SOURCE_ROOT}/agent_build/requirement-files/frozen-binaries-requirements.txt"

# Save pipe cache to reuse it in future.
save_to_cache pip "$pip_cache_dir"




