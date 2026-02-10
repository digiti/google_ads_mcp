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

"""Recommendation tools for the Google Ads API."""

from typing import Any

from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.tools.api import get_ads_client


@mcp.tool()
def get_recommendations(
    customer_id: str,
    recommendation_types: list[str] | None = None,
    login_customer_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
  """Gets optimization recommendations for a customer.

  Args:
      customer_id: The customer ID containing only digits.
      recommendation_types: Optional recommendation type enum names.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Recommendation records.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  google_ads_service: Any = ads_client.get_service("GoogleAdsService")

  query = (
      "SELECT "
      "recommendation.resource_name, "
      "recommendation.type, "
      "recommendation.dismissed, "
      "recommendation.campaign, "
      "recommendation.ad_group "
      "FROM recommendation"
  )
  if recommendation_types:
    enum_values = ", ".join(recommendation_types)
    query = f"{query} WHERE recommendation.type IN ({enum_values})"

  try:
    rows = google_ads_service.search(customer_id=customer_id, query=query)
    recommendations = []
    for row in rows:
      recommendations.append(
          {
              "resource_name": row.recommendation.resource_name,
              "recommendation_id": row.recommendation.resource_name.split("/")[
                  -1
              ],
              "type": row.recommendation.type_.name,
              "dismissed": row.recommendation.dismissed,
              "campaign": row.recommendation.campaign,
              "ad_group": row.recommendation.ad_group,
          }
      )
    return {"recommendations": recommendations}
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def apply_recommendation(
    customer_id: str,
    recommendation_id: str,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Applies a recommendation by ID.

  Args:
      customer_id: The customer ID containing only digits.
      recommendation_id: The recommendation ID containing only digits.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Applied recommendation metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  recommendation_service: Any = ads_client.get_service("RecommendationService")
  google_ads_service: Any = ads_client.get_service("GoogleAdsService")

  recommendation_resource_name = google_ads_service.recommendation_path(
      customer_id,
      recommendation_id,
  )

  try:
    operation: Any = ads_client.get_type("ApplyRecommendationOperation")
    operation.resource_name = recommendation_resource_name
    response = recommendation_service.apply_recommendation(
        customer_id=customer_id,
        operations=[operation],
    )
    return {
        "resource_name": response.results[0].resource_name,
        "recommendation_id": recommendation_id,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc


@mcp.tool()
def dismiss_recommendation(
    customer_id: str,
    recommendation_id: str,
    login_customer_id: str | None = None,
) -> dict[str, str]:
  """Dismisses a recommendation by ID.

  Args:
      customer_id: The customer ID containing only digits.
      recommendation_id: The recommendation ID containing only digits.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Dismissed recommendation metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  recommendation_service: Any = ads_client.get_service("RecommendationService")
  google_ads_service: Any = ads_client.get_service("GoogleAdsService")

  recommendation_resource_name = google_ads_service.recommendation_path(
      customer_id,
      recommendation_id,
  )

  try:
    operation: Any = ads_client.get_type(
        "DismissRecommendationRequest.DismissRecommendationOperation"
    )
    operation.resource_name = recommendation_resource_name
    recommendation_service.dismiss_recommendation(
        customer_id=customer_id,
        operations=[operation],
    )
    return {
        "resource_name": recommendation_resource_name,
        "recommendation_id": recommendation_id,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
