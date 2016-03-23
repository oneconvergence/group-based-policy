#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


def log_info(log, msg):
    log.info(msg)


def log_debug(log, msg):
        log.debug(msg)


def log_error(log, msg):
    log.error(msg)


def log_warn(log, msg):
    log.warn(msg)


def log_exception(log, msg):
    log.exception(msg)
