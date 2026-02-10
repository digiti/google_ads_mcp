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

"""Keyword planner tools for the Google Ads API."""

from typing import Any

from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.tools.api import get_ads_client


@mcp.tool()
def generate_keyword_ideas(
    customer_id: str,
    keywords: list[str],
    page_url: str | None = None,
    language_id: str = "1000",
    geo_target_ids: list[str] | None = None,
    login_customer_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
  """Generates keyword ideas using seed keywords and optionally a page URL.

  Args:
      customer_id: The customer ID containing only digits.
      keywords: Seed keywords.
      page_url: Optional landing page URL.
      language_id: Language criterion ID. Defaults to 1000 (English).
      geo_target_ids: Optional geo target IDs.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Generated keyword ideas and metrics.
  """
  if not keywords and not page_url:
    raise ToolError("At least one of keywords or page_url is required")

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  keyword_plan_idea_service: Any = ads_client.get_service(
      "KeywordPlanIdeaService"
  )
  geo_target_constant_service: Any = ads_client.get_service(
      "GeoTargetConstantService"
  )
  google_ads_service: Any = ads_client.get_service("GoogleAdsService")
  keyword_plan_network_enum: Any = ads_client.enums.KeywordPlanNetworkEnum

  location_resource_names = []
  if geo_target_ids:
    location_resource_names = [
        geo_target_constant_service.geo_target_constant_path(target_id)
        for target_id in geo_target_ids
    ]

  try:
    request: Any = ads_client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = google_ads_service.language_constant_path(language_id)
    request.geo_target_constants = location_resource_names
    request.keyword_plan_network = (
        keyword_plan_network_enum.GOOGLE_SEARCH_AND_PARTNERS
    )

    if keywords and page_url:
      request.keyword_and_url_seed.url = page_url
      request.keyword_and_url_seed.keywords.extend(keywords)
    elif keywords:
      request.keyword_seed.keywords.extend(keywords)
    elif page_url:
      request.url_seed.url = page_url

    response = keyword_plan_idea_service.generate_keyword_ideas(
        request=request
    )
    ideas = []
    for idea in response:
      ideas.append(
          {
              "text": idea.text,
              "avg_monthly_searches": idea.keyword_idea_metrics.avg_monthly_searches,
              "competition": idea.keyword_idea_metrics.competition.name,
              "competition_index": idea.keyword_idea_metrics.competition_index,
              "low_top_of_page_bid_micros": (
                  idea.keyword_idea_metrics.low_top_of_page_bid_micros
              ),
              "high_top_of_page_bid_micros": (
                  idea.keyword_idea_metrics.high_top_of_page_bid_micros
              ),
          }
      )

    return {"ideas": ideas}
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
