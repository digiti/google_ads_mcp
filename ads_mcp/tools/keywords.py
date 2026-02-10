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

"""Keyword management tools for the Google Ads API."""

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
def add_keywords(
    customer_id: str,
    ad_group_id: str,
    keywords: list[str],
    match_type: str = "BROAD",
    login_customer_id: str | None = None,
) -> dict[str, list[str]]:
  """Adds positive keywords to an ad group.

  Args:
      customer_id: The customer ID containing only digits.
      ad_group_id: The ad group ID containing only digits.
      keywords: Keyword texts to add.
      match_type: Keyword match type enum name. Defaults to BROAD.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Resource names of created keyword criteria.
  """
  if not keywords:
    raise ToolError("keywords must not be empty")

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  ad_group_criterion_service: Any = ads_client.get_service(
      "AdGroupCriterionService"
  )
  ad_group_service: Any = ads_client.get_service("AdGroupService")
  ad_group_criterion_status_enum: Any = (
      ads_client.enums.AdGroupCriterionStatusEnum
  )

  try:
    operations = []
    for keyword_text in keywords:
      operation: Any = ads_client.get_type("AdGroupCriterionOperation")
      criterion = operation.create
      criterion.ad_group = ad_group_service.ad_group_path(
          customer_id, ad_group_id
      )
      criterion.status = ad_group_criterion_status_enum.ENABLED
      criterion.keyword.text = keyword_text
      criterion.keyword.match_type = _enum_value(
          ads_client.enums.KeywordMatchTypeEnum,
          match_type,
          "match_type",
      )
      operations.append(operation)

    response = ad_group_criterion_service.mutate_ad_group_criteria(
        customer_id=customer_id,
        operations=operations,
    )
    return {
        "keyword_resource_names": [
            result.resource_name for result in response.results
        ]
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def update_keyword_status(
    customer_id: str,
    criterion_id: str,
    ad_group_id: str,
    status: str,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Updates ad group keyword criterion status.

  Args:
      customer_id: The customer ID containing only digits.
      criterion_id: The criterion ID containing only digits.
      ad_group_id: The ad group ID containing only digits.
      status: Ad group criterion status enum name.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      The updated criterion resource name and status.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  ad_group_criterion_service: Any = ads_client.get_service(
      "AdGroupCriterionService"
  )

  try:
    operation: Any = ads_client.get_type("AdGroupCriterionOperation")
    criterion = operation.update
    criterion.resource_name = (
        ad_group_criterion_service.ad_group_criterion_path(
            customer_id,
            ad_group_id,
            criterion_id,
        )
    )
    criterion.status = _enum_value(
        ads_client.enums.AdGroupCriterionStatusEnum,
        status,
        "status",
    )
    operation.update_mask.paths.append("status")

    ad_group_criterion_service.mutate_ad_group_criteria(
        customer_id=customer_id,
        operations=[operation],
    )
    return {
        "criterion_resource_name": criterion.resource_name,
        "status": status,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def add_negative_keywords(
    customer_id: str,
    campaign_id: str,
    keywords: list[str],
    login_customer_id: str | None = None,
) -> dict[str, list[str]]:
  """Adds campaign-level negative keywords.

  Args:
      customer_id: The customer ID containing only digits.
      campaign_id: The campaign ID containing only digits.
      keywords: Negative keyword texts to add.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Resource names of created negative criteria.
  """
  if not keywords:
    raise ToolError("keywords must not be empty")

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  campaign_criterion_service: Any = ads_client.get_service(
      "CampaignCriterionService"
  )
  campaign_service: Any = ads_client.get_service("CampaignService")
  keyword_match_type_enum: Any = ads_client.enums.KeywordMatchTypeEnum

  try:
    operations = []
    for keyword_text in keywords:
      operation: Any = ads_client.get_type("CampaignCriterionOperation")
      criterion = operation.create
      criterion.campaign = campaign_service.campaign_path(
          customer_id, campaign_id
      )
      criterion.negative = True
      criterion.keyword.text = keyword_text
      criterion.keyword.match_type = keyword_match_type_enum.BROAD
      operations.append(operation)

    response = campaign_criterion_service.mutate_campaign_criteria(
        customer_id=customer_id,
        operations=operations,
    )
    return {
        "negative_keyword_resource_names": [
            result.resource_name for result in response.results
        ]
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
