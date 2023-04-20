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

"""
This script helps GitHub Actions CI/CD to get information about runners that can be run in a parallel jobs, that
has to decrease overall build time.
"""

import argparse
import copy
import json
import pathlib as pl
import subprocess
import sys
import strictyaml
import logging
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# This file can be executed as script. Add source root to the PYTHONPATH in order to be able to import
# local packages. All such imports also have to be done after that.

SCRIPT_PATH = pl.Path(__file__).absolute()
SOURCE_ROOT = SCRIPT_PATH.parent.parent.parent
sys.path.append(str(SOURCE_ROOT))


# Import modules that define any runner that is used during the builds.
# It is important to import them before the import of the 'ALL_RUNNERS' or otherwise, runners from missing mudules
# won't be presented in the "ALL_RUNNERS" final collection.
import tests.end_to_end_tests  # NOQA
import tests.end_to_end_tests.run_in_remote_machine.portable_pytest_runner # NOQA
import tests.end_to_end_tests.managed_packages_tests.conftest  # NOQA

# Import ALL_RUNNERS global collection only after all modules that define any runner are imported.
from agent_build_refactored.tools.runner import ALL_RUNNERS

from agent_build_refactored.tools.runner import Runner, RunnerStep, get_all_required_steps_stages, get_steps_with_missing_results, filter_steps_with_existing_output

# Suffix that is appended to all steps cache keys. CI/CD cache can be easily invalidated by changing this value.
CACHE_VERSION_SUFFIX = "v14"

used_builders = []

existing_runners = {}
builders_to_prebuilt_runners = {}


def get_all_used_steps():
    result = {}
    for runner_cls in ALL_RUNNERS:
        for step in runner_cls.get_all_steps(recursive=True):
            result[step.id] = step

    return result


all_used_steps: Dict[str, RunnerStep] = get_all_used_steps()


# def create_wrapper_runner_from_step(step: RunnerStep):
#     class StepWrapperRunner(Runner):
#         CLASS_NAME_ALIAS = f"{step_id}_pre_build"
#
#         @classmethod
#         def get_all_required_steps(cls) -> List[RunnerStep]:
#             return [step]
#
#     return StepWrapperRunner


def get_cacheable_steps_stages():
    global all_used_steps

    remaining_steps = all_used_steps.copy()
    result_stages = []

    while remaining_steps:
        current_stage = {}
        for step_id, step in remaining_steps.items():
            add = True

            for req_step_id, req_step in step.get_all_required_steps().items():
                if req_step_id in remaining_steps:
                    add = False
                    break

            if not add:
                continue

            _RunnerCls = existing_runners.get(step.id)
            if _RunnerCls is None:
                class _RunnerCls(Runner):
                    CLASS_NAME_ALIAS = f"{step_id}_pre_build"

                    @classmethod
                    def get_all_required_steps(cls) -> List[RunnerStep]:
                        return [step]

                existing_runners[step.id] = _RunnerCls

                fqdn = _RunnerCls.FULLY_QUALIFIED_NAME
                current_stage[fqdn] = step

        for runner_fqdn, step in current_stage.items():
            remaining_steps.pop(step.id, None)
        result_stages.append(current_stage)

    return result_stages


stages = get_all_required_steps_stages(steps=list(all_used_steps.values()))



a=10

# runner_levels = []
# for level_steps in levels:
#     current_runner_level = {}
#     for step_id, step in level_steps.items():
#         _RunnerCls = existing_runners.get(step.id)
#         if _RunnerCls is None:
#             class _RunnerCls(Runner):
#                 CLASS_NAME_ALIAS = f"{step_id}_pre_build"
#
#                 @classmethod
#                 def get_all_required_steps(cls) -> List[RunnerStep]:
#                     return [step]
#
#             existing_runners[step.id] = _RunnerCls
#
#         fqdn = _RunnerCls.FULLY_QUALIFIED_NAME
#         current_runner_level[fqdn] = {"step": step, "runner": _RunnerCls}
#
#     runner_levels.append(current_runner_level)


def get_missing_caches_matrices(input_missing_cache_keys_file: pl.Path):
    json_content = input_missing_cache_keys_file.read_text()
    missing_steps_ids = json.loads(json_content)


    logger.info("MISSING")
    logger.info(missing_steps_ids)

    filtered_stages = filter_steps_with_existing_output(
        stages=stages, steps_ids_with_missing_results=missing_steps_ids
    )

    matrices = []
    for stage in filtered_stages:
        matrix_include = []

        for step_wrapper_runner_fqdn, step in stage.items():

            required_steps_ids = []
            for req_step in step.get_all_required_steps():
                required_steps_ids.append(req_step.id)

            matrix_include.append(
                {
                    "step_runner_fqdn": step_wrapper_runner_fqdn,
                    "step_id": step.id,
                    "name": step.name,
                    "required_steps": sorted(required_steps_ids),
                    "cache_version_suffix": CACHE_VERSION_SUFFIX,
                }
            )

        matrix = {"include": matrix_include}
        matrices.append(matrix)

    return matrices


def generate_workflow_yaml():
    """
    This function generates yml file for workflow that run pre-built steps.

    """
    template_path = SCRIPT_PATH.parent / "reusable-run-cacheable-runner-steps-template.yml"
    template_ymp = strictyaml.load(template_path.read_text())
    workflow = template_ymp.data

    jobs = workflow["jobs"]

    run_pre_built_job_object_name = "run_pre_built_job"
    run_pre_built_job = jobs.pop(run_pre_built_job_object_name)

    pre_job_outputs = {}
    for counter in range(len(stages)):
        stage_run_pre_built_job = copy.deepcopy(run_pre_built_job)
        if counter > 0:
            previous_run_pre_built_job_object_name = (
                f"{run_pre_built_job_object_name}{counter - 1}"
            )
            stage_run_pre_built_job["needs"].append(
                previous_run_pre_built_job_object_name
            )
            stage_run_pre_built_job[
                "if"
            ] = f"${{{{ always() && (needs.{previous_run_pre_built_job_object_name}.result == 'success' || needs.{previous_run_pre_built_job_object_name}.result == 'skipped') && needs.pre_job.outputs.matrix_length{counter} != '0' }}}}"
        else:
            stage_run_pre_built_job[
                "if"
            ] = f"${{{{ needs.pre_job.outputs.matrix_length{counter} != '0' }}}}"

        stage_run_pre_built_job["name"] = f"{counter} ${{{{ matrix.name }}}}"
        stage_run_pre_built_job["strategy"][
            "matrix"
        ] = f"${{{{ fromJSON(needs.pre_job.outputs.matrix{counter}) }}}}"

        pre_job_outputs[
            f"matrix{counter}"
        ] = f"${{{{ steps.print_missing_caches_matrices.outputs.matrix{counter} }}}}"
        pre_job_outputs[
            f"matrix_length{counter}"
        ] = f"${{{{ steps.print_missing_caches_matrices.outputs.matrix_length{counter} }}}}"

        stage_run_pre_built_job_object_name = (
            f"{run_pre_built_job_object_name}{counter}"
        )
        jobs[stage_run_pre_built_job_object_name] = stage_run_pre_built_job

    pre_job = jobs["pre_job"]
    pre_job["outputs"] = pre_job_outputs

    workflow_path = SOURCE_ROOT / ".github/workflows/reusable-run-cacheable-runner-steps.yml"

    yaml_content = strictyaml.as_document(workflow).as_yaml()

    # Add notification comment, that this YAML was auto-generated.

    script_rel_path = SCRIPT_PATH.relative_to(SOURCE_ROOT)
    template_rel_path = template_path.relative_to(SOURCE_ROOT)
    comment = f"# IMPORTANT: Do not modify.\n" \
              f"# This workflow file is generated by the script '{script_rel_path}' from the template '{template_rel_path}'.\n" \
              f"# Modify those files in order to make changes to the workflow."

    yaml_content = f"{comment}\n{yaml_content}"
    workflow_path.write_text(yaml_content)


def update_files():
    """

    :return:
    """
    generate_workflow_yaml()

    # Update the "restore_steps_caches" action source.
    action_root = SOURCE_ROOT / ".github/actions/restore_steps_caches"

    ncc_executable = action_root / "node_modules/.bin/ncc"

    subprocess.run(
        [
            ncc_executable,
            "build",
            "index.js",
        ],
        cwd=action_root,
        check=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    missing_caches_matrices_parser = subparsers.add_parser(
        "get-missing-caches-matrices"
    )
    missing_caches_matrices_parser.add_argument(
        "--missing-steps-ids-file", required=True
    )

    all_cache_keys_parser = subparsers.add_parser("get-all-steps-ids")

    get_cache_version_suffix_parser = subparsers.add_parser("get-cache-version-suffix")

    update_files_parser = subparsers.add_parser("update-files")

    args = parser.parse_args()

    if args.command == "get-missing-caches-matrices":
        matrices = get_missing_caches_matrices(
            input_missing_cache_keys_file=pl.Path(args.missing_steps_ids_file),
        )
        print(json.dumps(matrices))
    elif args.command == "get-all-steps-ids":
        print(json.dumps(list(sorted(all_used_steps.keys()))))

    elif args.command == "update-files":
        update_files()
    elif args.command == "get-cache-version-suffix":
        print(CACHE_VERSION_SUFFIX)

    exit(0)

