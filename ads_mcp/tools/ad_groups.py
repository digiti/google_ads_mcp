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

"""Ad group management tools for the Google Ads API."""

from typing import Any

from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.tools.api import get_ads_client


def _enum_value(enum_type: Any, value: str, field_name: str) -> Any:
  """Gets an enum value from an enum type by name."""
  try:
    return getattr(enum_type, value)
  except AttributeError as exc:
    raise ToolError(f"Invalid {field_name}: {value}") from exc


@mcp.tool()
def create_ad_group(
    customer_id: str,
    campaign_id: str,
    name: str,
    cpc_bid_micros: int | None = None,
    status: str = "ENABLED",
    login_customer_id: str | None = None,
) -> dict[str, str | int]:
  """Creates an ad group under a campaign.

  Args:
      customer_id: The customer ID containing only digits.
      campaign_id: The campaign ID containing only digits.
      name: The ad group name.
      cpc_bid_micros: Optional max CPC in micros.
      status: Ad group status enum name. Defaults to ENABLED.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Created ad group metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  ad_group_service: Any = ads_client.get_service("AdGroupService")
  campaign_service: Any = ads_client.get_service("CampaignService")
  ad_group_type_enum: Any = ads_client.enums.AdGroupTypeEnum

  try:
    ad_group_operation: Any = ads_client.get_type("AdGroupOperation")
    ad_group = ad_group_operation.create
    ad_group.name = name
    ad_group.campaign = campaign_service.campaign_path(
        customer_id, campaign_id
    )
    ad_group.status = _enum_value(
        ads_client.enums.AdGroupStatusEnum,
        status,
        "status",
    )
    ad_group.type_ = ad_group_type_enum.SEARCH_STANDARD
    if cpc_bid_micros is not None:
      ad_group.cpc_bid_micros = cpc_bid_micros

    response = ad_group_service.mutate_ad_groups(
        customer_id=customer_id,
        operations=[ad_group_operation],
    )
    resource_name = response.results[0].resource_name
    return {
        "ad_group_resource_name": resource_name,
        "ad_group_id": resource_name.split("/")[-1],
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def update_ad_group(
    customer_id: str,
    ad_group_id: str,
    status: str | None = None,
    name: str | None = None,
    cpc_bid_micros: int | None = None,
    login_customer_id: str | None = None,
) -> dict[str, str | int]:
  """Updates ad group fields.

  Args:
      customer_id: The customer ID containing only digits.
      ad_group_id: The ad group ID containing only digits.
      status: Optional ad group status enum name.
      name: Optional ad group name.
      cpc_bid_micros: Optional max CPC in micros.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Updated ad group metadata.
  """
  if status is None and name is None and cpc_bid_micros is None:
    raise ToolError(
        "At least one of status, name, or cpc_bid_micros is required"
    )

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  ad_group_service: Any = ads_client.get_service("AdGroupService")

  try:
    ad_group_operation: Any = ads_client.get_type("AdGroupOperation")
    ad_group = ad_group_operation.update
    ad_group.resource_name = ad_group_service.ad_group_path(
        customer_id, ad_group_id
    )

    if status is not None:
      ad_group.status = _enum_value(
          ads_client.enums.AdGroupStatusEnum,
          status,
          "status",
      )
      ad_group_operation.update_mask.paths.append("status")
    if name is not None:
      ad_group.name = name
      ad_group_operation.update_mask.paths.append("name")
    if cpc_bid_micros is not None:
      ad_group.cpc_bid_micros = cpc_bid_micros
      ad_group_operation.update_mask.paths.append("cpc_bid_micros")

    ad_group_service.mutate_ad_groups(
        customer_id=customer_id,
        operations=[ad_group_operation],
    )
    return {
        "ad_group_resource_name": ad_group.resource_name,
        "ad_group_id": ad_group_id,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
