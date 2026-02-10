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

"""Change history tools for the Google Ads API."""

from typing import Any

from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.tools.api import get_ads_client


@mcp.tool()
def get_change_events(
    customer_id: str,
    start_date: str,
    end_date: str | None = None,
    resource_type: str | None = None,
    login_customer_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
  """Gets account change events from the change_event resource.

  Args:
      customer_id: The customer ID containing only digits.
      start_date: Start date in yyyy-mm-dd format.
      end_date: Optional end date in yyyy-mm-dd format. Defaults to start_date.
      resource_type: Optional ChangeEventResourceType enum name.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Change event records.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  google_ads_service = ads_client.get_service("GoogleAdsService")

  resolved_end_date = end_date or start_date
  where_clauses = [
      (
          "change_event.change_date_time BETWEEN "
          f"'{start_date} 00:00:00' AND '{resolved_end_date} 23:59:59'"
      )
  ]
  if resource_type:
    where_clauses.append(
        f"change_event.change_resource_type = {resource_type}"
    )
  where_sql = " AND ".join(where_clauses)

  query = (
      "SELECT "
      "change_event.resource_name, "
      "change_event.change_date_time, "
      "change_event.change_resource_type, "
      "change_event.change_resource_name, "
      "change_event.user_email, "
      "change_event.client_type, "
      "change_event.resource_change_operation "
      "FROM change_event "
      f"WHERE {where_sql} "
      "ORDER BY change_event.change_date_time DESC"
  )

  try:
    rows = google_ads_service.search(customer_id=customer_id, query=query)
    events = []
    for row in rows:
      events.append(
          {
              "resource_name": row.change_event.resource_name,
              "change_date_time": row.change_event.change_date_time,
              "change_resource_type": row.change_event.change_resource_type.name,
              "change_resource_name": row.change_event.change_resource_name,
              "user_email": row.change_event.user_email,
              "client_type": row.change_event.client_type.name,
              "resource_change_operation": (
                  row.change_event.resource_change_operation.name
              ),
          }
      )
    return {"events": events}
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
