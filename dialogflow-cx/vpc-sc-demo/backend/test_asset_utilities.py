# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module for testing asset_utilities.py."""

import json

import asset_utilities
import pytest
import requests
from conftest import MockReturnObject, assert_response
from google.oauth2 import service_account
from invoke import MockContext as MockContextBase
from mock import patch


class MockResult:  # pylint: disable=too-few-public-methods
    """Class for mocking return value of invoke.Promise.join()."""

    def __init__(self, exited, stdout, stderr):
        """Mock expected attributes."""
        self.exited = exited
        self.stdout = stdout
        self.stderr = stderr


class MockPromise:  # pylint: disable=too-few-public-methods
    """Class for mocking expected interfact of invoke.Promise."""

    def __init__(self, result):
        """Initialize with pre-defined behavior for mock."""
        self.result = result

    def join(self):
        """Implement join interface."""
        return self.result


class MockContext(MockContextBase):
    """Enhance invoke.MockContext to work with Promise."""

    def run(self, *args, **kwargs):
        """Modify result of run method to return cached response."""
        return self.result

    def set_result(self, result):
        """Set up result value for run after context is initialized."""
        self.result = result  # pylint: disable=attribute-defined-outside-init


@pytest.mark.hermetic
def test_get_access_policy_title_success():
    """Test get_access_policy_title, success"""
    with patch.object(
        requests,
        "get",
        return_value=MockReturnObject(
            200,
            {"title": "MOCK_TITLE"},
        ),
    ):
        result = asset_utilities.get_access_policy_title(
            "MOCK_TOKEN", "MOCK_ACCESS_POLICY_ID"
        )
    assert result == {"access_policy_title": "MOCK_TITLE"}


@pytest.mark.hermetic
def test_get_access_policy_title_server_error():
    """Test get_access_policy_title, server error"""
    with patch.object(
        requests,
        "get",
        return_value=MockReturnObject(
            500,
            ["SERVER_ERROR"],
        ),
    ):
        result = asset_utilities.get_access_policy_title(
            "MOCK_TOKEN", "MOCK_ACCESS_POLICY_ID"
        )
    assert_response(result, 500, ["SERVER_ERROR"])


@pytest.fixture
def request_args():
    """Default values for request_args as a pytest fixture."""
    return {
        "project_id": "MOCK_PROJECT_ID",
        "bucket": "MOCK_BUCKET",
        "region": "MOCK_REGION",
    }


@pytest.mark.hermetic
@pytest.mark.parametrize(
    "access_policy_title,debug,expected",
    [
        (
            None,
            False,
            {
                "GOOGLE_OAUTH_ACCESS_TOKEN": "MOCK_TOKEN",
                "TF_VAR_project_id": "MOCK_PROJECT_ID",
                "TF_VAR_bucket": "MOCK_BUCKET",
                "TF_VAR_region": "MOCK_REGION",
                "TF_VAR_access_policy_title": "null",
            },
        ),
        (
            "MOCK_ACCESS_POLICY_TITLE",
            False,
            {
                "GOOGLE_OAUTH_ACCESS_TOKEN": "MOCK_TOKEN",
                "TF_VAR_project_id": "MOCK_PROJECT_ID",
                "TF_VAR_bucket": "MOCK_BUCKET",
                "TF_VAR_region": "MOCK_REGION",
                "TF_VAR_access_policy_title": "MOCK_ACCESS_POLICY_TITLE",
            },
        ),
        (
            "MOCK_ACCESS_POLICY_TITLE",
            True,
            {
                "GOOGLE_OAUTH_ACCESS_TOKEN": "MOCK_TOKEN",
                "TF_VAR_project_id": "MOCK_PROJECT_ID",
                "TF_VAR_bucket": "MOCK_BUCKET",
                "TF_VAR_region": "MOCK_REGION",
                "TF_VAR_access_policy_title": "MOCK_ACCESS_POLICY_TITLE",
                "TF_LOG": "DEBUG",
            },
        ),
    ],
)
def test_get_terraform_env(  # pylint: disable=redefined-outer-name
    access_policy_title, debug, expected, request_args
):
    """Test get_terraform_env."""
    if access_policy_title:
        request_args["access_policy_title"] = "MOCK_ACCESS_POLICY_TITLE"

    result = asset_utilities.get_terraform_env("MOCK_TOKEN", request_args, debug=debug)
    assert result == expected


@pytest.mark.hermetic
@pytest.mark.parametrize(
    "debug,exited",
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_tf_init(debug, exited, request_args):  # pylint: disable=redefined-outer-name
    """Test tf_init."""
    with patch.object(service_account, "Credentials", return_value="MOCK_CREDENTIALS"):

        context = MockContext()
        context.set_result(
            MockPromise(MockResult(exited, "MOCK_STDOUT", "MOCK_STDERR"))
        )
        result = asset_utilities.tf_init(
            context,
            "MOCK_MODULE",
            "MOCK_WORKDIR",
            asset_utilities.get_terraform_env(
                "MOCK_ACCESS_TOKEN",
                request_args,
                debug=debug,
            ),
            "MOCK_PREFIX",
        )
        if not exited:
            assert result is None
        else:
            assert result.status_code == 500
            assert result.response == [
                json.dumps(
                    {
                        "status": "ERROR",
                        "stdout": "MOCK_STDOUT",
                        "stderr": "MOCK_STDERR",
                    }
                ).encode()
            ]


@pytest.mark.hermetic
@pytest.mark.parametrize(
    "debug,message",
    [
        (False, json.dumps({"@level": "info"})),
        (
            False,
            json.dumps({"@level": "error", "type": "MOCK_TYPE", "hook": "MOCK_HOOK"}),
        ),
        (True, json.dumps({"@level": "info"})),
        (
            True,
            json.dumps({"@level": "error", "type": "MOCK_TYPE", "hook": "MOCK_HOOK"}),
        ),
    ],
)
def test_tf_plan(debug, message, request_args):  # pylint: disable=redefined-outer-name
    """Test tf_plan."""
    mock_stdout = "\n".join([message])
    context = MockContext()
    context.set_result(MockPromise(MockResult(False, mock_stdout, "MOCK_STDERR")))
    with patch.object(service_account, "Credentials", return_value="MOCK_CREDENTIALS"):
        result = asset_utilities.tf_plan(
            context,
            "MOCK_MODULE",
            "MOCK_WORKDIR",
            asset_utilities.get_terraform_env(
                "MOCK_ACCESS_TOKEN",
                request_args,
                debug=debug,
            ),
        )

    if debug:
        assert result is None
    else:
        if "error" in message:
            assert_response(
                result,
                500,
                {
                    "status": "ERROR",
                    "errors": [
                        {"@level": "error", "type": "MOCK_TYPE", "hook": "MOCK_HOOK"}
                    ],
                },
            )
        else:
            assert result == {
                "hooks": {
                    "refresh_start": [],
                    "refresh_complete": [],
                    "apply_complete": [],
                    "apply_start": [],
                }
            }


@pytest.mark.hermetic
@pytest.mark.parametrize(
    "debug,message",
    [
        (False, json.dumps({"@level": "info"})),
        (False, json.dumps({"@level": "error", "error": "MOCK_ERROR"})),
        (True, json.dumps({"@level": "info"})),
        (True, json.dumps({"@level": "error", "error": "MOCK_ERROR"})),
    ],
)
def test_tf_apply(debug, message, request_args):  # pylint: disable=redefined-outer-name
    """Test tf_apply."""
    message_list = [message, "BAD_LINE"]
    mock_stdout = "\n".join(message_list)
    assert len(mock_stdout.split("\n")) == len(message_list)
    context = MockContext()
    context.set_result(MockPromise(MockResult(False, mock_stdout, "MOCK_STDERR")))
    with patch.object(service_account, "Credentials", return_value="MOCK_CREDENTIALS"):
        result = asset_utilities.tf_apply(
            context,
            "MOCK_MODULE",
            "MOCK_WORKDIR",
            asset_utilities.get_terraform_env(
                "MOCK_ACCESS_TOKEN",
                request_args,
                debug=debug,
            ),
            False,
        )
    if debug or "error" not in message:
        assert result is None
    else:
        assert len(result.response) == 1
        assert result.status_code == 500
        response_dict = json.loads(result.response[0].decode())
        assert response_dict == {
            "status": "ERROR",
            "errors": [{"@level": "error", "error": "MOCK_ERROR"}],
        }


@pytest.mark.hermetic
@pytest.mark.parametrize(
    "debug,exited,stdout",
    [
        (False, True, "MOCK_STDOUT"),
        (True, False, "MOCK_STDOUT"),
        (True, True, "MOCK_STDOUT"),
        (False, False, "MOCK_STDOUT"),
    ]
    + [
        (False, False, "\n".join(resource_list))
        for resource_list in asset_utilities.RESOURCE_GROUP.values()
    ],
)
def test_tf_state_list(
    debug,
    exited,
    stdout,
    request_args,  # pylint: disable=redefined-outer-name
):
    """Test tf_state_list."""
    context = MockContext()
    context.set_result(MockPromise(MockResult(exited, stdout, "MOCK_STDERR")))
    with patch.object(service_account, "Credentials", return_value="MOCK_CREDENTIALS"):
        result = asset_utilities.tf_state_list(
            context,
            "MOCK_MODULE",
            "MOCK_WORKDIR",
            asset_utilities.get_terraform_env(
                "MOCK_ACCESS_TOKEN",
                request_args,
                debug=debug,
            ),
        )
    if exited:
        assert_response(
            result,
            500,
            {
                "status": "ERROR",
                "stdout": "MOCK_STDOUT",
                "stderr": "MOCK_STDERR",
            },
        )
    else:
        if stdout != "MOCK_STDOUT":
            assert len(result["resources"]) == 1 + len(stdout.split())
        else:
            assert result == {"resources": ["MOCK_STDOUT"]}
