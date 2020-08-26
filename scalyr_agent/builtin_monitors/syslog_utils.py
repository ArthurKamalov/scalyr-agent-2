from __future__ import absolute_import
import os
import re
import copy
from string import Template

import six
from scalyr_agent import scalyr_logging

from scalyr_agent.json_lib import JsonObject

from scalyr_agent.builtin_monitors.journald_utils import LogConfigManager


class SyslogLogFormatter(scalyr_logging.BaseFormatter):
    """Formatter used for the logs produced by the journald monitor.

    In general, it formats each line as:
        time (with milliseconds)
        component (`journald_monitor()` so we don't have to have ugly hashes in the log line for extended config.)
        message (the logged message)
    """

    def __init__(self):
        scalyr_logging.BaseFormatter.__init__(
            self, "%(asctime)s [syslog_monitor()] %(message)s", "metric-formatter"
        )


class SyslogLogConfigManager(LogConfigManager):
    def __init__(
        self,
        global_config,
        formatter,
        max_log_size=20 * 1024 * 1024,
        max_log_rotations=2,
        extra_config=None,
    ):
        LogConfigManager.__init__(
            self,
            global_config,
            formatter,
            max_log_size=max_log_size,
            max_log_rotations=max_log_rotations,
            extra_config=extra_config,
        )
        self.default_parser = self._extra_config.get("parser")
        self.file_template_string = self._extra_config.get("message_log")

    def initialize(self):
        """ Generate the config matchers for this manager from the global config
        """
        config_matchers = []
        for config in self._global_config.syslog_log_configs:
            config_matcher = self.create_config_matcher(config)
            config_matchers.append(config_matcher)
        # Add a catchall matcher at the end in case one was not configured
        config_matchers.append(self.create_config_matcher({}))

        return config_matchers

    def create_config_matcher(self, conf):
        """ Create a function that will return a log configuration when passed in data that matches that config.
        Intended to be overwritten by users of LogConfigManager to match their own use case.
        If passed an empty dictionary in `conf` this should create a catchall matcher with default configuration.

        @param conf: Logger configuration in the form of a dictionary or JsonObject, that a matcher should be created for.
        @return: Logger configuration in the form of a dictionary or JsonObject if this matcher matches the passed
        in data, None otherwise
        """
        config = copy.deepcopy(conf)
        if "syslog_app" not in config:
            config["syslog_app"] = ".*"
        if "parser" not in config:
            config["parser"] = self.default_parser
        if "attributes" not in config:
            config["attributes"] = JsonObject({"monitor": "agentSyslog"})
        file_template = Template(self.file_template_string)
        regex = re.compile(config["syslog_app"])
        match_hash = six.text_type(hash(config["syslog_app"]))
        if config["syslog_app"] == ".*":
            match_hash = ""
        full_path = os.path.join(
            self._global_config.agent_log_path,
            file_template.safe_substitute({"ID": match_hash}),
        )
        matched_config = JsonObject({"parser": "syslog", "path": full_path})
        matched_config.update(config)

        def config_matcher(unit):
            if regex.match(unit) is not None:
                return matched_config
            return None

        return config_matcher
