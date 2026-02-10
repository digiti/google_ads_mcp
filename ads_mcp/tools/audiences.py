# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Audience tools for customer list creation and membership management."""

import hashlib
from typing import Any

from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.tools.api import get_ads_client


def _normalize_and_hash(value: str, remove_all_whitespace: bool) -> str:
  """Normalizes and hashes a value with SHA-256."""
  normalized = value.strip().lower()
  if remove_all_whitespace:
    normalized = "".join(normalized.split())
  return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _build_offline_user_data_job_operations(
    ads_client: Any,
    emails: list[str],
    phone_numbers: list[str],
    remove: bool,
) -> list[Any]:
  """Builds operations for offline user data jobs."""
  operations = []

  for email in emails:
    operation: Any = ads_client.get_type("OfflineUserDataJobOperation")
    user_data: Any = ads_client.get_type("UserData")
    user_identifier: Any = ads_client.get_type("UserIdentifier")
    user_identifier.hashed_email = _normalize_and_hash(email, True)
    user_data.user_identifiers.append(user_identifier)
    if remove:
      operation.remove = user_data
    else:
      operation.create = user_data
    operations.append(operation)

  for phone_number in phone_numbers:
    operation: Any = ads_client.get_type("OfflineUserDataJobOperation")
    user_data: Any = ads_client.get_type("UserData")
    user_identifier: Any = ads_client.get_type("UserIdentifier")
    user_identifier.hashed_phone_number = _normalize_and_hash(
        phone_number, True
    )
    user_data.user_identifiers.append(user_identifier)
    if remove:
      operation.remove = user_data
    else:
      operation.create = user_data
    operations.append(operation)

  return operations


@mcp.tool()
def create_customer_list(
    customer_id: str,
    list_name: str,
    description: str | None = None,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Creates a Customer Match user list.

  Args:
      customer_id: The customer ID containing only digits.
      list_name: The user list name.
      description: Optional user list description.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Created user list metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  user_list_service: Any = ads_client.get_service("UserListService")
  customer_match_upload_key_type_enum: Any = (
      ads_client.enums.CustomerMatchUploadKeyTypeEnum
  )

  try:
    operation: Any = ads_client.get_type("UserListOperation")
    user_list = operation.create
    user_list.name = list_name
    user_list.description = description or "Customer Match list"
    user_list.crm_based_user_list.upload_key_type = (
        customer_match_upload_key_type_enum.CONTACT_INFO
    )
    user_list.membership_life_span = 30

    response = user_list_service.mutate_user_lists(
        customer_id=customer_id,
        operations=[operation],
    )
    resource_name = response.results[0].resource_name
    return {
        "user_list_resource_name": resource_name,
        "user_list_id": resource_name.split("/")[-1],
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def add_customer_list_members(
    customer_id: str,
    user_list_id: str,
    emails: list[str] | None = None,
    phone_numbers: list[str] | None = None,
    login_customer_id: str | None = None,
) -> dict[str, str | int]:
  """Adds members to a Customer Match list via OfflineUserDataJobService.

  Args:
      customer_id: The customer ID containing only digits.
      user_list_id: The user list ID containing only digits.
      emails: Optional plain text emails to normalize and hash.
      phone_numbers: Optional phone numbers to normalize and hash.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Offline user data job metadata.
  """
  email_values = emails or []
  phone_values = phone_numbers or []
  if not email_values and not phone_values:
    raise ToolError("At least one of emails or phone_numbers is required")

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  google_ads_service: Any = ads_client.get_service("GoogleAdsService")
  offline_job_service: Any = ads_client.get_service(
      "OfflineUserDataJobService"
  )
  offline_user_data_job_type_enum: Any = (
      ads_client.enums.OfflineUserDataJobTypeEnum
  )

  try:
    user_list_resource_name = google_ads_service.user_list_path(
        customer_id,
        user_list_id,
    )

    offline_job: Any = ads_client.get_type("OfflineUserDataJob")
    offline_job.type_ = (
        offline_user_data_job_type_enum.CUSTOMER_MATCH_USER_LIST
    )
    offline_job.customer_match_user_list_metadata.user_list = (
        user_list_resource_name
    )

    create_response = offline_job_service.create_offline_user_data_job(
        customer_id=customer_id,
        job=offline_job,
    )
    operations = _build_offline_user_data_job_operations(
        ads_client,
        email_values,
        phone_values,
        remove=False,
    )
    add_request: Any = ads_client.get_type(
        "AddOfflineUserDataJobOperationsRequest"
    )
    add_request.resource_name = create_response.resource_name
    add_request.enable_partial_failure = True
    add_request.operations = operations
    add_response = offline_job_service.add_offline_user_data_job_operations(
        request=add_request,
    )

    offline_job_service.run_offline_user_data_job(
        resource_name=create_response.resource_name
    )
    return {
        "offline_user_data_job_resource_name": create_response.resource_name,
        "operation_count": len(operations),
        "partial_failure_code": add_response.partial_failure_error.code,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def remove_customer_list_members(
    customer_id: str,
    user_list_id: str,
    emails: list[str] | None = None,
    phone_numbers: list[str] | None = None,
    login_customer_id: str | None = None,
) -> dict[str, str | int]:
  """Removes members from a Customer Match list via OfflineUserDataJobService.

  Args:
      customer_id: The customer ID containing only digits.
      user_list_id: The user list ID containing only digits.
      emails: Optional plain text emails to normalize and hash.
      phone_numbers: Optional phone numbers to normalize and hash.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Offline user data job metadata.
  """
  email_values = emails or []
  phone_values = phone_numbers or []
  if not email_values and not phone_values:
    raise ToolError("At least one of emails or phone_numbers is required")

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  google_ads_service: Any = ads_client.get_service("GoogleAdsService")
  offline_job_service: Any = ads_client.get_service(
      "OfflineUserDataJobService"
  )
  offline_user_data_job_type_enum: Any = (
      ads_client.enums.OfflineUserDataJobTypeEnum
  )

  try:
    user_list_resource_name = google_ads_service.user_list_path(
        customer_id,
        user_list_id,
    )

    offline_job: Any = ads_client.get_type("OfflineUserDataJob")
    offline_job.type_ = (
        offline_user_data_job_type_enum.CUSTOMER_MATCH_USER_LIST
    )
    offline_job.customer_match_user_list_metadata.user_list = (
        user_list_resource_name
    )

    create_response = offline_job_service.create_offline_user_data_job(
        customer_id=customer_id,
        job=offline_job,
    )
    operations = _build_offline_user_data_job_operations(
        ads_client,
        email_values,
        phone_values,
        remove=True,
    )
    add_request: Any = ads_client.get_type(
        "AddOfflineUserDataJobOperationsRequest"
    )
    add_request.resource_name = create_response.resource_name
    add_request.enable_partial_failure = True
    add_request.operations = operations
    add_response = offline_job_service.add_offline_user_data_job_operations(
        request=add_request,
    )

    offline_job_service.run_offline_user_data_job(
        resource_name=create_response.resource_name
    )
    return {
        "offline_user_data_job_resource_name": create_response.resource_name,
        "operation_count": len(operations),
        "partial_failure_code": add_response.partial_failure_error.code,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
