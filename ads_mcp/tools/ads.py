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

"""Ad management tools for the Google Ads API."""

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
def create_responsive_search_ad(
    customer_id: str,
    ad_group_id: str,
    headlines: list[str],
    descriptions: list[str],
    final_urls: list[str],
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Creates a responsive search ad in an ad group.

  Args:
      customer_id: The customer ID containing only digits.
      ad_group_id: The ad group ID containing only digits.
      headlines: Headline text list.
      descriptions: Description text list.
      final_urls: Final URL list.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Created ad metadata.
  """
  if not headlines:
    raise ToolError("headlines must not be empty")
  if not descriptions:
    raise ToolError("descriptions must not be empty")
  if not final_urls:
    raise ToolError("final_urls must not be empty")

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  ad_group_ad_service: Any = ads_client.get_service("AdGroupAdService")
  ad_group_service: Any = ads_client.get_service("AdGroupService")
  ad_group_ad_status_enum: Any = ads_client.enums.AdGroupAdStatusEnum

  try:
    operation: Any = ads_client.get_type("AdGroupAdOperation")
    ad_group_ad = operation.create
    ad_group_ad.ad_group = ad_group_service.ad_group_path(
        customer_id, ad_group_id
    )
    ad_group_ad.status = ad_group_ad_status_enum.PAUSED

    for headline_text in headlines:
      headline_asset: Any = ads_client.get_type("AdTextAsset")
      headline_asset.text = headline_text
      ad_group_ad.ad.responsive_search_ad.headlines.append(headline_asset)

    for description_text in descriptions:
      description_asset: Any = ads_client.get_type("AdTextAsset")
      description_asset.text = description_text
      ad_group_ad.ad.responsive_search_ad.descriptions.append(
          description_asset
      )

    ad_group_ad.ad.final_urls.extend(final_urls)

    response = ad_group_ad_service.mutate_ad_group_ads(
        customer_id=customer_id,
        operations=[operation],
    )
    resource_name = response.results[0].resource_name
    ad_id = resource_name.split("~")[-1]
    return {
        "ad_group_ad_resource_name": resource_name,
        "ad_id": ad_id,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def update_ad_status(
    customer_id: str,
    ad_id: str,
    status: str,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Updates an ad status through its ad group ad record.

  Args:
      customer_id: The customer ID containing only digits.
      ad_id: The ad ID containing only digits.
      status: AdGroupAd status enum name.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Updated ad metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  google_ads_service: Any = ads_client.get_service("GoogleAdsService")
  ad_group_ad_service: Any = ads_client.get_service("AdGroupAdService")

  query = (
      "SELECT ad_group.id "
      "FROM ad_group_ad "
      f"WHERE ad_group_ad.ad.id = {ad_id} "
      "LIMIT 1"
  )

  try:
    rows = google_ads_service.search(customer_id=customer_id, query=query)
    row = next(iter(rows), None)
    if row is None:
      raise ToolError(f"Ad not found: {ad_id}")

    ad_group_id = str(row.ad_group.id)

    operation: Any = ads_client.get_type("AdGroupAdOperation")
    ad_group_ad = operation.update
    ad_group_ad.resource_name = ad_group_ad_service.ad_group_ad_path(
        customer_id,
        ad_group_id,
        ad_id,
    )
    ad_group_ad.status = _enum_value(
        ads_client.enums.AdGroupAdStatusEnum,
        status,
        "status",
    )
    operation.update_mask.paths.append("status")

    ad_group_ad_service.mutate_ad_group_ads(
        customer_id=customer_id,
        operations=[operation],
    )
    return {
        "ad_group_ad_resource_name": ad_group_ad.resource_name,
        "status": status,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
