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

"""Campaign management tools for the Google Ads API."""

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
def create_campaign(
    customer_id: str,
    name: str,
    advertising_channel_type: str,
    status: str = "PAUSED",
    budget_amount_micros: int | None = None,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Creates a new campaign and campaign budget.

  Args:
      customer_id: The customer ID containing only digits.
      name: The campaign name.
      advertising_channel_type: Campaign channel enum name, for example SEARCH.
      status: Campaign status enum name. Defaults to PAUSED.
      budget_amount_micros: Budget amount in micros. Defaults to 1000000.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Created campaign and budget metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  campaign_budget_service: Any = ads_client.get_service(
      "CampaignBudgetService"
  )
  campaign_service: Any = ads_client.get_service("CampaignService")
  budget_delivery_method_enum: Any = ads_client.enums.BudgetDeliveryMethodEnum

  try:
    budget_operation: Any = ads_client.get_type("CampaignBudgetOperation")
    budget = budget_operation.create
    budget.name = f"{name} Budget"
    budget.delivery_method = budget_delivery_method_enum.STANDARD
    budget.amount_micros = budget_amount_micros or 1_000_000
    budget.explicitly_shared = False

    budget_response = campaign_budget_service.mutate_campaign_budgets(
        customer_id=customer_id,
        operations=[budget_operation],
    )
    budget_resource_name = budget_response.results[0].resource_name

    campaign_operation: Any = ads_client.get_type("CampaignOperation")
    campaign = campaign_operation.create
    campaign.name = name
    campaign.status = _enum_value(
        ads_client.enums.CampaignStatusEnum,
        status,
        "status",
    )
    campaign.advertising_channel_type = _enum_value(
        ads_client.enums.AdvertisingChannelTypeEnum,
        advertising_channel_type,
        "advertising_channel_type",
    )
    campaign.campaign_budget = budget_resource_name

    campaign_response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation],
    )
    campaign_resource_name = campaign_response.results[0].resource_name

    return {
        "campaign_resource_name": campaign_resource_name,
        "campaign_id": campaign_resource_name.split("/")[-1],
        "budget_resource_name": budget_resource_name,
        "budget_id": budget_resource_name.split("/")[-1],
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def update_campaign_status(
    customer_id: str,
    campaign_id: str,
    status: str,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Updates a campaign status.

  Args:
      customer_id: The customer ID containing only digits.
      campaign_id: The campaign ID containing only digits.
      status: Campaign status enum name.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      The updated campaign resource name and status.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  campaign_service: Any = ads_client.get_service("CampaignService")

  try:
    campaign_operation: Any = ads_client.get_type("CampaignOperation")
    campaign = campaign_operation.update
    campaign.resource_name = campaign_service.campaign_path(
        customer_id, campaign_id
    )
    campaign.status = _enum_value(
        ads_client.enums.CampaignStatusEnum,
        status,
        "status",
    )
    campaign_operation.update_mask.paths.append("status")

    campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation],
    )
    return {
        "campaign_resource_name": campaign.resource_name,
        "status": status,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def update_campaign_budget(
    customer_id: str,
    campaign_id: str,
    budget_amount_micros: int,
    login_customer_id: str | None = None,
) -> dict[str, str | int]:
  """Updates the budget amount for a campaign.

  Args:
      customer_id: The customer ID containing only digits.
      campaign_id: The campaign ID containing only digits.
      budget_amount_micros: New budget amount in micros.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      The updated budget resource name and amount.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  google_ads_service: Any = ads_client.get_service("GoogleAdsService")
  campaign_budget_service: Any = ads_client.get_service(
      "CampaignBudgetService"
  )

  query = (
      "SELECT campaign.campaign_budget "
      "FROM campaign "
      f"WHERE campaign.id = {campaign_id} "
      "LIMIT 1"
  )

  try:
    rows = google_ads_service.search(customer_id=customer_id, query=query)
    row = next(iter(rows), None)
    if row is None:
      raise ToolError(f"Campaign not found: {campaign_id}")

    budget_resource_name = row.campaign.campaign_budget

    budget_operation: Any = ads_client.get_type("CampaignBudgetOperation")
    budget = budget_operation.update
    budget.resource_name = budget_resource_name
    budget.amount_micros = budget_amount_micros
    budget_operation.update_mask.paths.append("amount_micros")

    campaign_budget_service.mutate_campaign_budgets(
        customer_id=customer_id,
        operations=[budget_operation],
    )
    return {
        "budget_resource_name": budget_resource_name,
        "amount_micros": budget_amount_micros,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
